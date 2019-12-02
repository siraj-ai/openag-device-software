# Import standard python modules
import json, os, ssl, sys, time, subprocess
import paho.mqtt.client as mqtt

# Import python types
from typing import Dict, Tuple, Optional, Any, NamedTuple, Callable

# Import device utilities
from device.utilities import logger
from device.utilities.state.main import State
from device.utilities.iot import registration, tokens

# Import module elements
from device.iot import commands
from device.iot import messages


# Settings file will have hostname and port(s)
MQTT_SETTINGS_FILE = os.path.join("device","iot","setups","local_mqtt.json")

# Initialize message types


# TODO: Write tests
# TODO: Catch specific exceptions
# TODO: Add static type checking


class PubSub:
    """Handles communication with a local MQTT service"""

    # Initialize state
    is_initialized = False

    def __init__(
        self,
        ref_self: Any,
        on_connect: Callable,
        on_disconnect: Callable,
        on_publish: Callable,
        on_message: Callable,
        on_subscribe: Callable,
        on_log: Callable,
    ) -> None:
        """Initializes pubsub handler."""

        # Initialize parameters
        self.ref_self = ref_self
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_publish = on_publish
        self.on_message = on_message
        self.on_subscribe = on_subscribe
        self.on_log = on_log
        # Used to swich ports on failure to communicate to MQTT
        self.mqtt_port_choice = 0
        self.mqtt_broker = None
        self.mqtt_ports = []

        # Initialize logger
        logging_level = os.getenv("LOG_LEVEL_iot_pubsub")
        self.logger = logger.Logger("PubSub", "iot")
        if logging_level is not None:
            self.logger.setLevel(logging_level)

    ##### HELPER FUNCTIONS ####################################################

    def initialize(self) -> None:
        """Initializes pubsub client."""
        self.logger.debug("Initializing")
        try:
            self.load_mqtt_config()
            self.create_mqtt_client()
            self.is_initialized = True
        except Exception as e:
            message = "Unable to initialize, unhandled exception: {}".format(type(e))
            self.logger.exception(message)
            self.is_initialized = False

    def load_mqtt_config(self) -> None:
        """Loads mqtt config."""
        self.logger.debug("Loading mqtt config")
        with open(MQTT_SETTINGS_FILE) as settings_file:
            settings = json.load(settings_file)
            try:
                self.mqtt_broker = settings["broker"]
                self.mqtt_ports = settings["ports"]
            except KeyError as e:
                message = "Unable to load {}, key {} is required".format(MQTT_SETTINGS_FILE, e)
                self.logger.critical(message)
                raise

        # Load settings from environment variables
        try:
            # self.project_id = os.environ["GCLOUD_PROJECT"]
            # self.cloud_region = os.environ["GCLOUD_REGION"]
            # self.registry_id = os.environ["GCLOUD_DEV_REG"]
            self.device_id = registration.device_id()
            # self.private_key_filepath = os.environ["IOT_PRIVATE_KEY"]
            # self.ca_certs = os.environ["CA_CERTS"]
        except KeyError as e:
            message = "Unable to load pubsub config, key {} is required".format(e)
            self.logger.critical(message)
            raise

        # Initialize client id
        # self.client_id = "projects/{}/locations/{}/registries/{}/devices/{}".format(
        #    self.project_id, self.cloud_region, self.registry_id, self.device_id
        #)
        self.client_id = "openag/devices/{}".format(self.device_id)

        # Initialize config topic
        self.config_topic = "/devices/{}/config".format(self.device_id)

        # Initialize commands topic
        self.command_topic = "/devices/{}/commands/#".format(self.device_id)

        # Initialize event topic
        test_telemetry_topic = os.environ.get("IOT_TEST_TOPIC")
        if test_telemetry_topic is not None:
            self.telemetry_topic = "/devices/{}/{}".format(self.device_id, test_telemetry_topic)
            self.logger.debug("Publishing to test topic: {}".format(self.telemetry_topic))
        else:
            self.telemetry_topic = "/devices/{}/events".format(self.device_id)

    def create_mqtt_client(self) -> None:
        """Creates an mqtt client. Returns client and assocaited json web token."""
        self.logger.debug("Creating mqtt client")

        # Initialize client object
        self.client = mqtt.Client(client_id=self.client_id, userdata=self.ref_self)

        # Create json web token
        # try:
        #     self.json_web_token = tokens.create_json_web_token(
        #         project_id=self.project_id,
        #         private_key_filepath=self.private_key_filepath,
        #     )
        # except Exception as e:
        #     message = "Unable to create client, unhandled exception: {}".format(type(e))
        #     self.logger.exception(message)
        #     return
        #
        # # Pass json web token to google cloud iot core, note username is ignored
        # self.client.username_pw_set(
        #     username="unused", password=self.json_web_token.encoded
        # )
        #
        # # Enable SSL/TLS support
        # self.client.tls_set(ca_certs=self.ca_certs, tls_version=ssl.PROTOCOL_TLSv1_2)

        # Register message callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish

        # Connect to the Google MQTT bridge
        self.client.connect(self.mqtt_broker, self.mqtt_ports[self.mqtt_port_choice])

        # Subscribe to topicsf
        # self.subscribe_to_topics()
    
    def subscribe_to_topics(self):
        self.logger.info("Subscribing to topics")
        self.client.subscribe(self.config_topic, qos=1)
        self.client.subscribe(self.command_topic, qos=1)

    def next_port(self):
        if len(self.mqtt_ports) > 1:
            self.mqtt_port_choice = (self.mqtt_port_choice + 1) % len(self.mqtt_ports)
        return self.mqtt_port_choice

    def update(self) -> None:
        """Updates pubsub client."""

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning(
                "Tried to update before client initialized, initializing client"
            )
            self.initialize()
            return

        # Check if json webtoken is expired, if so renew client
        #if self.json_web_token.is_expired:
        #    self.create_mqtt_client()  # TODO: Renew instead of re-create
        #    self.subscribe_to_topics()

        # Update mqtt client
        try:
            self.client.loop()
        except Exception as e:
            message = "Unable to update, unhandled exception: {}".format(type(e))
            self.logger.exception(message)

    ##### PUBLISH FUNCTIONS ###################################################

    def publish_boot_message(self, message: Dict) -> None:
        """Publishes boot message."""
        self.logger.debug("Publishing boot message")

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning("Tried to publish before client initialized")
            return

        # Publish message
        message_json = json.dumps(message)
        self.publish_command_reply(messages.BOOT_MESSAGE, message_json)

    def publish_status_message(self, message: Dict) -> None:
        """Publishes status message."""
        self.logger.debug("Publishing status message")

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning("Tried to publish before client initialized")
            return

        # Publish message
        message_json = json.dumps(message)
        self.publish_command_reply(messages.STATUS_MESSAGE, message_json)

    def publish_recipe_event(self, device_id: str, action: str, name: str) -> None:
        self.logger.debug(f"Publishing recipe event {action} {name} message from {device_id}.")

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning("Tried to publish before client initialized")
            return

        # Build message
        message = {
            "messageType": messages.RECIPE_EVENT_MESSAGE,
            "device_id": device_id,
            "action": action,
            "name": name,
        }
        message_json = json.dumps(message)

        # Publish message
        try:
            self.client.publish(self.telemetry_topic, message_json, qos=1)
        except Exception as e:
            error_message = "Unable to publish recipe event message, "
            "unhandled exception: {}".format(type(e))
            self.logger.exception(error_message)


    ##### PRIVATE PUBLISH FUNCTIONS? #########################################

    def publish_command_reply(self, command: str, values: str) -> None:
        """Publish a reply to a previously received command. Don't we need the 
        message id then?"""
        self.logger.debug("Publishing command reply")

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning("Tried to publish before client initialized")
            return

        # Build message
        message = {
            "messageType": messages.COMMAND_REPLY_MESSAGE,
            "var": command,
            "values": values,
        }
        message_json = json.dumps(message)

        # Publish message
        try:
            self.client.publish(self.telemetry_topic, message_json, qos=1)
        except Exception as e:
            error_message = "Unable to publish command reply, "
            "unhandled exception: {}".format(type(e))
            self.logger.exception(error_message)

    def publish_environment_variable(
        self, variable_name: str, values_dict: Dict
    ) -> None:
        """Publish a single environment variable."""
        self.logger.debug(
            "Publishing environment variable message: {}".format(variable_name)
        )
        # self.logger.debug("variable_name = {}".format(variable_name))
        # self.logger.debug("values_dict = {}".format(values_dict))

        # Check if client is initialized
        if not self.is_initialized:
            self.logger.warning("Tried to publish message before client initialized")
            return

        # Validate the values
        valid = False
        for vname in values_dict:
            val = values_dict[vname]
            if val is not None:
                valid = True
                break
        if not valid:
            return

        # Build values json
        # TODO: Change this from string manipulation to dict creation then json.dumps
        count = 0
        values_json = "{'values':["
        for vname in values_dict:
            val = values_dict[vname]

            if count > 0:
                values_json += ","
            count += 1

            if isinstance(val, float):
                val = "{0:.2f}".format(val)
                values_json += "{'name':'%s', 'type':'float', 'value':%s}" % (
                    vname,
                    val,
                )

            elif isinstance(val, int):
                values_json += "{'name':'%s', 'type':'int', 'value':%s}" % (vname, val)

            else:  # assume str
                values_json += "{'name':'%s', 'type':'str', 'value':'%s'}" % (
                    vname,
                    val,
                )
        values_json += "]}"

        # Initialize publish message
        message = {
            "messageType": messages.ENVIRONMENT_VARIABLE_MESSAGE,
            "var": variable_name,
            "values": values_json,
        }

        # Publish message
        try:
            message_json = json.dumps(message)
            self.client.publish(self.telemetry_topic, message_json, qos=1)
        except Exception as e:
            error_message = "Unable to publish environment variables, "
            "unhandled exception: {}".format(type(e))
            self.logger.exception(error_message)

    # TODO: Need to make a local version of this
    def upload_image(self, file_name: str) -> None:
        pass
        # self.logger.debug("Uploading binary image")
        #
        # if not self.is_initialized:
        #     self.logger.warning("Tried to publish before client initialized")
        #     return
        #
        # if file_name == None or len(file_name) == 0:
        #     error_message = "Unable to publish image, file name "
        #     "`{}` is invalid".format(file_name)
        #     self.logger.error(error_message)
        #     raise ValueError(error_message)
        #
        # # Get the camera name and image type from the file_name:
        # # /Users/rob/yada/yada/2019-05-08-T23-18-31Z_Camera-Top.png
        # base = ''
        # try:
        #     base = os.path.basename(file_name) # get just the file from path
        #     fn1 = base.split("_")  # delimiter between datetime & camera name
        #     fn2 = fn1[1]           # 'Camera-Top.png'
        #     fn3 = fn2.split(".")   # delimiter between file and extension
        #     camera_name = fn3[0]   # 'Camera-Top'
        # except:
        #     camera_name = base
        #
        # device_id = registration.device_id()
        # upload_file_name = '{}_{}'.format(device_id, base)
        #
        # # commented URL below is for running the firebase cloud function
        # # service locally for testing
        # #URL = 'http://localhost:5000/fb-func-test/us-central1/saveImage'
        #
        # URL = 'https://us-central1-fb-func-test.cloudfunctions.net/saveImage'
        # DATA = 'data=@{};filename={}'.format(file_name, upload_file_name)
        #
        # try:
        #     # Use curl to do a multi part form post of the binary data (fast) to
        #     # our firebase cloud function that puts the image in the GCP
        #     # storage bucket.
        #     res = subprocess.run(['curl', '--silent', URL, '-F', DATA])
        #     self.logger.debug("Uploaded file: {}".format(upload_file_name))
        #
        #     # Publish a message indicating that we uploaded the image to the
        #     # public bucket written by the firebase cloud function, and we need
        #     # to move the image to the usual images bucket we have been using.
        #     message = {
        #         "messageType": messages.IMAGE_MESSAGE,
        #         "varName": camera_name,
        #         "fileName": upload_file_name,
        #     }
        #
        #     message_json = json.dumps(message)
        #     self.client.publish(self.telemetry_topic, message_json, qos=1)
        #
        # except Exception as e:
        #     error_message = "Unable to publish binary image, unhandled "
        #     "exception: {}".format(type(e))
        #     self.logger.exception(error_message)
