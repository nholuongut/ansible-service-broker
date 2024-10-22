//
// Copyright (c) 2018 Red Hat, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

package app

import (
	"context"
	"fmt"
	"net"
	"os"
	"strings"
	"time"

	k8sauthorization "github.com/automationbroker/bundle-lib/authorization/k8s"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/serializer"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/apiserver/pkg/authentication/authenticatorfactory"
	genericapiserver "k8s.io/apiserver/pkg/server"
	genericoptions "k8s.io/apiserver/pkg/server/options"
	"k8s.io/apiserver/pkg/server/routes"
	"k8s.io/client-go/informers"
	authenticationclient "k8s.io/client-go/kubernetes/typed/authentication/v1beta1"

	"github.com/automationbroker/bundle-lib/bundle"
	"github.com/automationbroker/bundle-lib/clients"
	blmetrics "github.com/automationbroker/bundle-lib/metrics"
	"github.com/automationbroker/bundle-lib/registries"
	agnosticruntime "github.com/automationbroker/bundle-lib/runtime"
	"github.com/automationbroker/config"
	"github.com/openshift/ansible-service-broker/pkg/auth"
	"github.com/openshift/ansible-service-broker/pkg/broker"
	"github.com/openshift/ansible-service-broker/pkg/dao"
	"github.com/openshift/ansible-service-broker/pkg/handler"
	logutil "github.com/openshift/ansible-service-broker/pkg/util/logging"
	"github.com/openshift/ansible-service-broker/pkg/version"
	"github.com/prometheus/client_golang/prometheus"
	log "github.com/sirupsen/logrus"
)

var (
	// Scheme - the runtime scheme
	Scheme = runtime.NewScheme()
	// Codecs -k8s codecs for the scheme
	Codecs = serializer.NewCodecFactory(Scheme)
)

const (
	// ClusterURLPreFix - prefix for the ansible service broker.
	ClusterURLPreFix = "/osb"
	// MsgBufferSize - The buffer for the message channel.
	MsgBufferSize = 20
	// SubscriberTimeout - the amount of time in seconds that subscribers have to complete their action
	SubscriberTimeout = 3
)

// App - All the application pieces that are installed.
type App struct {
	broker   *broker.AnsibleBroker
	args     Args
	config   *config.Config
	dao      dao.Dao
	registry []registries.Registry
	engine   *broker.WorkEngine
}

func apiServer(config *config.Config,
	providers []auth.Provider) (*genericapiserver.GenericAPIServer, error) {

	log.Debug("calling NewSecureServingOptions")
	secureServing := genericoptions.NewSecureServingOptions()
	secureServing.ServerCert = genericoptions.GeneratableKeyCert{CertKey: genericoptions.CertKey{
		CertFile: config.GetString("broker.ssl_cert"),
		KeyFile:  config.GetString("broker.ssl_cert_key"),
	}}
	secureServing.BindPort = 1338
	secureServing.BindAddress = net.ParseIP("0.0.0.0")
	if err := secureServing.MaybeDefaultWithSelfSignedCerts("localhost", nil, []net.IP{net.ParseIP("127.0.0.1")}); err != nil {
		return nil, fmt.Errorf("error creating self-signed certificates: %v", err)
	}

	serverConfig := genericapiserver.NewConfig(Codecs)
	if err := secureServing.ApplyTo(serverConfig); err != nil {
		log.Debugf("error applying to %#v", err)
		return nil, err
	}

	k8s, err := clients.Kubernetes()
	if err != nil {
		return nil, err
	}
	if len(providers) == 0 {
		client, err := authenticationclient.NewForConfig(k8s.ClientConfig)
		if err != nil {
			return nil, err
		}

		authn := genericoptions.NewDelegatingAuthenticationOptions()
		authenticationConfig := authenticatorfactory.DelegatingAuthenticatorConfig{
			Anonymous:               true,
			TokenAccessReviewClient: client.TokenReviews(),
			CacheTTL:                authn.CacheTTL,
		}
		authenticator, _, err := authenticationConfig.New()
		if err != nil {
			return nil, err
		}
		serverConfig.Authenticator = authenticator

		authz := genericoptions.NewDelegatingAuthorizationOptions()
		if err := authz.ApplyTo(serverConfig); err != nil {
			return nil, err
		}
	}

	log.Debug("Creating k8s apiserver")
	s := informers.NewSharedInformerFactory(k8s.Client, 2*time.Hour)
	metav1.AddToGroupVersion(Scheme, metav1.Unversioned)
	return serverConfig.Complete(s).New("ansible-service-broker", genericapiserver.EmptyDelegate)
}

// CreateApp - Creates the application with the given registries if they are
// passed in, otherwise it will read them from the configuration.
func CreateApp(args Args, regs []registries.Registry) App {
	var err error
	app := App{args: args}

	fmt.Println("============================================================")
	fmt.Println("==           Creating Ansible Service Broker...           ==")
	fmt.Println("============================================================")

	// TODO: Let's take all these validations and delegate them to the client
	// pkg.
	if app.config, err = config.CreateConfig(app.args.ConfigFile); err != nil {
		os.Stderr.WriteString("ERROR: Failed to read config file\n")
		os.Stderr.WriteString(err.Error() + "\n")
		os.Exit(1)
	}
	c := logutil.LogConfig{
		LogFile: app.config.GetString("log.logfile"),
		Stdout:  app.config.GetBool("log.stdout"),
		Level:   app.config.GetString("log.level"),
		Color:   app.config.GetBool("log.color"),
	}
	if err = logutil.InitializeLog(c); err != nil {
		os.Stderr.WriteString("ERROR: Failed to initialize logger\n")
		os.Stderr.WriteString(err.Error())
		os.Exit(1)
	}

	// Show version in logs for better debugging
	log.Infof("Ansible Service Broker Version: %v", version.Version)
	// Initializing clients as soon as we have deps ready.
	err = initClients(app.config)
	if err != nil {
		log.Error(err.Error())
		os.Exit(1)
	}

	// Initialize Runtime
	log.Debug("Connecting to Cluster")
	brokerNS := app.config.GetString("openshift.namespace")
	agnosticruntime.NewRuntime(agnosticruntime.Configuration{StateMasterNamespace: brokerNS})
	agnosticruntime.Provider.ValidateRuntime()
	if err != nil {
		log.Error(err.Error())
		os.Exit(1)
	}

	log.Debug("Connecting Dao")
	app.dao, err = dao.NewDao(app.config)
	if err != nil {
		log.Error(err.Error())
		os.Exit(1)
	}

	// if we have custom registries, use those instead of those configured in
	// the configmap
	if len(regs) > 0 {
		log.Info("Using the supplied custom registries.")
		for _, reg := range regs {
			app.registry = append(app.registry, reg)
		}
	} else {
		log.Debug("Connecting Registry")
		for _, config := range app.config.GetSubConfigArray("registry") {
			c := registries.Config{
				URL:           config.GetString("url"),
				User:          config.GetString("user"),
				Pass:          config.GetString("pass"),
				Token:         config.GetString("token"),
				Org:           config.GetString("org"),
				Tag:           config.GetString("tag"),
				Type:          config.GetString("type"),
				Name:          config.GetString("name"),
				Images:        config.GetSliceOfStrings("images"),
				Namespaces:    config.GetSliceOfStrings("namespaces"),
				Fail:          config.GetBool("fail_on_error"),
				WhiteList:     config.GetSliceOfStrings("white_list"),
				BlackList:     config.GetSliceOfStrings("black_list"),
				AuthType:      config.GetString("auth_type"),
				AuthName:      config.GetString("auth_name"),
				Runner:        config.GetString("runner"),
				SkipVerifyTLS: config.GetBool("skip_verify_tls"),
			}

			reg, err := registries.NewRegistry(c, app.config.GetString("openshift.namespace"))
			if err != nil {
				log.Errorf(
					"Failed to initialize %v Registry err - %v \n", config.GetString("name"), err)
				os.Exit(1)
			}
			app.registry = append(app.registry, reg)
		}
	}

	validateRegistryNames(app.registry)

	log.Debug("Initializing WorkEngine")
	stateSubscriber := broker.NewJobStateSubscriber(app.dao)
	app.engine = broker.NewWorkEngine(MsgBufferSize, SubscriberTimeout, app.dao)
	err = app.engine.AttachSubscriber(
		stateSubscriber,
		broker.ProvisionTopic)
	if err != nil {
		log.Errorf("Failed to attach subscriber to WorkEngine: %s", err.Error())
		os.Exit(1)
	}
	err = app.engine.AttachSubscriber(
		stateSubscriber,
		broker.DeprovisionTopic)
	if err != nil {
		log.Errorf("Failed to attach subscriber to WorkEngine: %s", err.Error())
		os.Exit(1)
	}
	err = app.engine.AttachSubscriber(
		stateSubscriber,
		broker.UpdateTopic)
	if err != nil {
		log.Errorf("Failed to attach subscriber to WorkEngine: %s", err.Error())
		os.Exit(1)
	}
	err = app.engine.AttachSubscriber(
		stateSubscriber,
		broker.BindingTopic)
	if err != nil {
		log.Errorf("Failed to attach subscriber to WorkEngine: %s", err.Error())
		os.Exit(1)
	}
	err = app.engine.AttachSubscriber(
		stateSubscriber,
		broker.UnbindingTopic)
	if err != nil {
		log.Errorf("Failed to attach subscriber to WorkEngine: %s", err.Error())
		os.Exit(1)
	}

	rules := []bundle.AssociationRule{}
	for _, secretConfig := range app.config.GetSubConfigArray("secrets") {
		rules = append(rules, bundle.AssociationRule{
			BundleName: secretConfig.GetString("apb_name"),
			Secret:     secretConfig.GetString("secret"),
		})
	}
	bundle.InitializeSecretsCache(rules)

	log.Debug("Creating AnsibleBroker")
	// Initialize the cluster config.
	clusterConfig := bundle.ClusterConfig{
		PullPolicy:           app.config.GetString("openshift.image_pull_policy"),
		SandboxRole:          app.config.GetString("openshift.sandbox_role"),
		Namespace:            brokerNS,
		KeepNamespace:        app.config.GetBool("openshift.keep_namespace"),
		KeepNamespaceOnError: app.config.GetBool("openshift.keep_namespace_on_error"),
	}
	bundle.InitializeClusterConfig(clusterConfig)

	// initialize the work factory
	workFactory := broker.NewWorkFactory()
	if app.broker, err = broker.NewAnsibleBroker(
		app.dao, app.registry, *app.engine, app.config.GetSubConfig("broker"), brokerNS, workFactory,
	); err != nil {
		log.Error("Failed to create AnsibleBroker\n")
		log.Error(err.Error())
		os.Exit(1)
	}

	return app
}

// Recover - Recover the application
// TODO: Make this a go routine once we have a strong and well tested
// recovery sequence.
func (a *App) Recover() {
	msg, err := a.broker.Recover()

	if err != nil {
		log.Error(err.Error())
	}

	log.Info(msg)
}

// Start - Will start the application to listen on the specified port.
func (a *App) Start() {
	// TODO: probably return an error or some sort of message such that we can
	// see if we need to go any further.
	fmt.Println("============================================================")
	fmt.Println("==           Starting Ansible Service Broker...           ==")
	fmt.Println("============================================================")

	if a.config.GetBool("broker.recovery") {
		log.Info("Initiating Recovery Process")
		a.Recover()
	}

	if a.config.GetBool("broker.bootstrap_on_startup") {
		log.Info("Broker configured to bootstrap on startup")
		log.Info("Attempting bootstrap...")
		if _, err := a.broker.Bootstrap(); err != nil {
			log.Error("Failed to bootstrap on startup!")
			log.Error(err.Error())
			os.Exit(1)
		}
		log.Info("Broker successfully bootstrapped on startup")
	}

	interval, err := time.ParseDuration(a.config.GetString("broker.refresh_interval"))
	log.Debugf("RefreshInterval: %v", interval.String())
	if err != nil {
		log.Error(err.Error())
		log.Error("Not using a refresh interval")
	} else {
		ticker := time.NewTicker(interval)
		ctx, cancelFunc := context.WithCancel(context.Background())
		defer cancelFunc()
		go func() {
			for {
				select {
				case v := <-ticker.C:
					log.Infof("Broker configured to refresh specs every %v seconds", interval)
					log.Infof("Attempting bootstrap at %v", v.UTC())
					if _, err := a.broker.Bootstrap(); err != nil {
						log.Error("Failed to bootstrap")
						log.Error(err.Error())
					}
					log.Info("Broker successfully bootstrapped")
				case <-ctx.Done():
					ticker.Stop()
					return
				}
			}
		}()
	}
	//Retrieve the auth providers if basic auth is configured.
	providers := auth.GetProviders(a.config)

	genericserver, servererr := apiServer(a.config, providers)
	if servererr != nil {
		log.Errorf("problem creating apiserver. %v", servererr)
		panic(servererr)
	}

	userAuthRuleToCheck := a.config.GetString("broker.user_auth_rule")
	if userAuthRuleToCheck == "" {
		// Maintains backwards compatibility if the new user_auth_rule config value
		// is missing. Previously, we simply checked for "access".
		userAuthRuleToCheck = "access"
	}
	authorizer, err := k8sauthorization.NewAuthorizer("automationbroker.io", userAuthRuleToCheck, "create")
	var clusterURL = ClusterURLPreFix

	daHandler := prometheus.InstrumentHandler(
		"ansible-service-broker",
		handler.NewHandler(a.broker, a.config, clusterURL, providers, authorizer),
	)

	genericserver.Handler.NonGoRestfulMux.HandlePrefix(fmt.Sprintf("%v/", clusterURL), daHandler)

	defaultMetrics := routes.DefaultMetrics{}
	defaultMetrics.Install(genericserver.Handler.NonGoRestfulMux)

	blmetrics.RegisterCollector()

	log.Infof("Listening on https://%s", genericserver.SecureServingInfo.Listener.Addr().String())

	log.Info("Ansible Service Broker Starting")
	err = genericserver.PrepareRun().Run(wait.NeverStop)
	log.Errorf("unable to start ansible service broker - %v", err)

	//TODO: Add Flag so we can still use the old way of doing this.
}

func initClients(c *config.Config) error {
	// Designed to panic early if we cannot construct required clients.
	// this likely means we're in an unrecoverable configuration or environment.
	// Best we can do is alert the operator as early as possible.
	//
	// Deliberately forcing the injection of deps here instead of running as a
	// method on the app. Forces developers at authorship time to think about
	// dependencies / make sure things are ready.
	log.Info("Initializing clients...")

	if strings.ToLower(c.GetString("dao.type")) != "crd" {

		log.Debug("Trying to connect to etcd")
		// Initialize the etcd configuration
		con := clients.EtcdConfig{
			EtcdHost:       c.GetString("dao.etcd_host"),
			EtcdPort:       c.GetInt("dao.etcd_port"),
			EtcdCaFile:     c.GetString("dao.etcd_ca_file"),
			EtcdClientKey:  c.GetString("dao.etcd_client_key"),
			EtcdClientCert: c.GetString("dao.etcd_client_cert"),
		}
		clients.InitEtcdConfig(con)

		etcdClient, err := clients.Etcd()
		if err != nil {
			return err
		}

		ctx, cancelFunc := context.WithCancel(context.Background())
		defer cancelFunc()

		version, err := etcdClient.GetVersion(ctx)
		if err != nil {
			return err
		}

		log.Infof("Etcd Version [Server: %s, Cluster: %s]", version.Server, version.Cluster)
	}

	_, err := clients.Kubernetes()
	if err != nil {
		return err
	}

	return nil
}

func validateRegistryNames(registrys []registries.Registry) {
	names := map[string]bool{}
	for _, registry := range registrys {
		if _, ok := names[registry.RegistryName()]; ok {
			panic(fmt.Sprintf("Name of registry: %v must be unique", registry.RegistryName()))
		}
		names[registry.RegistryName()] = true
	}
}
