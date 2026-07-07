"""
Created on June 28, 2016

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

import importlib

import index  # type: ignore


class Organization:
    def __init__(self, botengine, organization_id):
        """
        Constructor
        :param botengine: BotEngine environment
        :param organization_id: Organization ID
        """
        # Organization ID
        self.organization_id = int(organization_id)

        # Born on date
        self.born_on = botengine.get_timestamp()

        # Organization domain name (short name)
        self.organization_domain_name = None

        # Organization descriptive name (long human readable name)
        self.organization_descriptive_name = None

        # All Organization Intelligence modules
        self.intelligence_modules = {}

        # Bot version tracking
        self.version = None

    def new_version(self, botengine):
        """
        New bot version - runs one time when we are executing a new bot version

        :param botengine: BotEngine environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">new_version() New bot version detected"
        )

        # Synchronize all intelligence modules (adding/removing based on index changes)
        self._sync_intelligence_modules(botengine)

        # Trigger new_version() on all intelligence modules
        for intelligence_module_id in self.intelligence_modules:
            try:
                self.intelligence_modules[intelligence_module_id].new_version(botengine)
            except Exception as e:
                import traceback

                botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                    "|new_version() Error triggering new_version on intelligence module: intelligence_module={} error={} traceback={}".format(
                        intelligence_module_id, str(e), str(traceback.format_exc())
                    )
                )

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("<new_version()")

    def initialize(self, botengine):
        """
        Initialize all services
        :param botengine:
        """
        # Synchronize info
        org = botengine.get_organization_info()
        self.organization_domain_name = org.get("domainName")
        self.organization_descriptive_name = org.get("organizationName")

        # Synchronize intelligence capabilities
        self._sync_intelligence_modules(botengine)

        # Intelligence module execution
        for i in self.intelligence_modules:
            self.intelligence_modules[i].parent = self
            self.intelligence_modules[i].initialize(botengine)

    def _sync_intelligence_modules(self, botengine):
        """
        Synchronize intelligence modules with the index
        :param botengine: BotEngine environment
        """
        if len(self.intelligence_modules) != len(
            index.MICROSERVICES.get("ORGANIZATION_MICROSERVICES", [])
        ):
            # Add more intelligence modules
            for intelligence_info in index.MICROSERVICES.get(
                "ORGANIZATION_MICROSERVICES", []
            ):
                if intelligence_info["module"] not in self.intelligence_modules:
                    try:
                        microservice = importlib.import_module(
                            intelligence_info["module"]
                        )
                        class_ = getattr(microservice, intelligence_info["class"])
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                            "|_sync_intelligence_modules() Adding organization intelligence module: "
                            + str(intelligence_info["module"])
                        )
                        intelligence_object = class_(botengine, self)
                        self.intelligence_modules[intelligence_info["module"]] = (
                            intelligence_object
                        )

                    except Exception as e:
                        import traceback

                        botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                            "|_sync_intelligence_modules() Could not add organization intelligence module: module={} error={} traceback={}".format(
                                str(intelligence_info["module"]),
                                str(e),
                                str(traceback.format_exc()),
                            )
                        )

            # Remove intelligence modules that no longer exist
            modules_to_delete = []
            for module_name in self.intelligence_modules.keys():
                found = False
                for intelligence_info in index.MICROSERVICES.get(
                    "ORGANIZATION_MICROSERVICES", []
                ):
                    if intelligence_info["module"] == module_name:
                        found = True
                        break

                if not found:
                    botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                        "|_sync_intelligence_modules() Deleting organization intelligence module: "
                        + str(module_name)
                    )
                    modules_to_delete.append(module_name)

            for module_name in modules_to_delete:
                del self.intelligence_modules[module_name]

        # Order intelligence modules alphabetically then by execution priority
        self.intelligence_modules = dict(
            sorted(self.intelligence_modules.items(), key=lambda module: module[0])
        )
        execution_priorities = {}
        for intelligence_info in index.MICROSERVICES.get(
            "ORGANIZATION_MICROSERVICES", []
        ):
            execution_priorities[intelligence_info["module"]] = intelligence_info.get(
                "execution_priority", 0
            )

        self.intelligence_modules = dict(
            sorted(
                self.intelligence_modules.items(),
                key=lambda module: execution_priorities.get(module[0], 0),
                reverse=True,
            )
        )

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
        """
        for intelligence_id in self.intelligence_modules:
            self.intelligence_modules[intelligence_id].question_answered(botengine, question)

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Updated
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Data Stream content
        """
        for intelligence_id in self.intelligence_modules:
            try:
                self.intelligence_modules[intelligence_id].datastream_updated(
                    botengine, address, content
                )
            except Exception as e:
                import traceback

                botengine.get_logger(f"{__name__}.{__class__.__name__}").warn(
                    "|datastream_updated() Error delivering datastream message to organization intelligence module (continuing execution): error={} traceback={}".format(
                        str(e), str(traceback.format_exc())
                    )
                )

    def async_data_request_ready(self, botengine, reference, data_dict):
        """
        A botengine.request_data() asynchronous request for CSV data is ready.
        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param device_csv_dict: { 'device_id': 'csv data string' }
        """
        for intelligence_id in self.intelligence_modules:
            if not hasattr(
                self.intelligence_modules[intelligence_id], "async_data_request_ready"
            ):
                continue
            try:
                self.intelligence_modules[intelligence_id].async_data_request_ready(
                    botengine, reference, data_dict
                )
            except Exception as e:
                import traceback

                botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                    "|async_data_request_ready() Error delivering async_data_request_ready to intelligence module {}: error={} traceback={}".format(
                        intelligence_id, str(e), str(traceback.format_exc())
                    )
                )

    def schedule_fired(self, botengine, schedule_id):
        """
        Schedule Fired.
        It is this location's responsibility to notify all microservices
        :param botengine: BotEngine environment
        """
        # Location intelligence modules
        for intelligence_id in self.intelligence_modules:
            self.intelligence_modules[intelligence_id].schedule_fired(botengine, schedule_id)

    def timer_fired(self, botengine, intelligence_id, argument):
        """
        Timer fired
        :param botengine: BotEngine environment
        :param intelligence_id: Microservice ID that fired
        :param argument: Optional argument
        """
        for microservice_object in self.intelligence_modules.values():
            if intelligence_id == microservice_object.intelligence_id:
                microservice_object.timer_fired(botengine, argument)
                return

    def get_microservice_by_id(self, botengine, microservice_id):
        """
        Get a microservice ("intelligence module") by its id ("intelligence_id").
        Sorry we named them 'intelligence modules' at first when they were really microservices.

        :param microservice_id: Microservice ID
        :return: Microservice object, or None if it doesn't exist.
        """
        # Search organization-level microservices
        for microservice in self.intelligence_modules.values():
            if hasattr(microservice, 'intelligence_id') and microservice.intelligence_id == microservice_id:
                return microservice

        return None

    def document_updated(self, botengine, document, request_id):
        """
        Document Updated
        :param botengine: BotEngine environment
        :param document: Updated document
        :param requestId: Current request ID
        """
        for intelligence_id in self.intelligence_modules:
            if not hasattr(self.intelligence_modules[intelligence_id], "document_updated"):
                continue
            self.intelligence_modules[intelligence_id].document_updated(
                botengine, document, request_id
            )

    # ===========================================================================
    # Data Stream Message delivery
    # ===========================================================================
    def distribute_datastream_message(
        self, botengine, address, content, internal=True, external=True
    ):
        """
        Distribute a data stream message both internally to any intelligence module within this bot,
        and externally to any other bots that might be listening.
        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Message content
        :param internal: True to deliver this message internally to any intelligence module that's listening (default)
        :param external: True to deliver this message externally to any other bot that's listening (default)
        """
        if internal:
            self.datastream_updated(botengine, address, content)

        if external:
            botengine.send_datastream_message(address, content)
