"""
Created on March 27, 2017

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""


from organization.organization import Organization


class Controller:
    """
    This is the main class that will coordinate all our sensors and behavior
    """

    def __init__(self):
        """
        Constructor
        """
        # A list of our organizations, where the key is the organization ID.
        self.organizations = {}

        # Last execution timestamp for debugging support
        self.exec_timestamp = 0

        # Last version of the bot
        self.version = None

    def initialize(self, botengine):
        """
        Initialize the controller.
        This is mandatory to call once for each new execution of the bot
        :param botengine: BotEngine environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(">initialize()")

        if hasattr(self, "exec_timestamp"):
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "|initialize() Last execution={}; Current execution={}".format(
                    self.exec_timestamp, botengine.get_timestamp()
                )
            )
        self.exec_timestamp = botengine.get_timestamp()

        if len(self.organizations) == 0:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "<initialize() No organizations"
            )
            return
        for key in self.organizations:
            self.organizations[key].initialize(botengine)
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug("<initialize()")

    def print_status(self, botengine):
        """
        Print the status of this object
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "Controller Status\nt-----\n\tself.organizations: {}\n\t-----".format(
                str(self.organizations)
            )
        )

    def get_intelligence_statistics(self, botengine):
        """
        Get the intelligence statistics for all locations
        :param botengine: BotEngine environment
        :return: List of statistics json

        Example:
        [
            {
                "name": "microservice_name",
                "calls": 3,
                "time": 280 # ms
            }
        ]
        """
        all_intelligence_module_statistics = []
        for organization_id in self.organizations:
            # Gather organization intelligence modules
            for intelligence_module in self.organizations[
                organization_id
            ].intelligence_modules.keys():
                all_intelligence_module_statistics.append(
                    (
                        intelligence_module,
                        self.organizations[organization_id]
                        .intelligence_modules[intelligence_module]
                        .get_statistics(botengine),
                    )
                )

        stats = []

        for (
            intelligence_module,
            intelligence_module_statistics,
        ) in all_intelligence_module_statistics:
            # Assign the microservice package name to the "name" field
            if (
                "intelligence" != intelligence_module.split(".")[0]
                or len(intelligence_module.split(".")) == 1
            ):
                continue

            # botengine.get_logger(f"{__name__}.{__class__.__name__}").debug("|get_intelligence_statistics() \t{} - {}".format(intelligence_module, intelligence_module_statistics))

            intelligence_module_package_name = intelligence_module.split(".")[1]
            # Aggregate intelligence module statistics by package name
            _stats = [
                stat
                for stat in stats
                if stat["name"] == intelligence_module_package_name
            ]
            if len(_stats) == 0:
                stat = {
                    "name": intelligence_module_package_name,
                    "calls": intelligence_module_statistics["calls"],
                    "time": intelligence_module_statistics["time"],
                }
                stats.append(stat)
            else:
                stat = _stats[0]
                stat["calls"] += intelligence_module_statistics["calls"]
                stat["time"] += intelligence_module_statistics["time"]

            # Remove floating point
            stat["time"] = int(stat["time"])

        return stats

    def track_new_and_deleted_organizations(self, botengine):
        """
        Track any new or deleted sub organizations
        :param botengine: Execution environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            ">track_new_and_deleted_organizations()"
        )

        # Track the organization this bot is running on
        organization_id = botengine.get_organization_id()
        if organization_id not in self.organizations:
            # The organization isn't being tracked yet, add it
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "|track_new_and_deleted_organizations() \t=> Now tracking organization "
                + str(organization_id)
            )
            self.organizations[organization_id] = Organization(
                botengine, organization_id
            )

        # # Update coordinates and track any sub organizations
        # for organization_access in botengine.get_organizations():
        #     organization = organization_access["organization"]
        #     if organization["organizationId"] in self.organizations:
        #         continue
        #     botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
        #         "|track_new_and_deleted_organizations() \t=> Now tracking sub-organization "
        #         + str(organization["organizationId"])
        #     )
        #     botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
        #         "|track_new_and_deleted_organizations() \t\tsub_type={}".format(organization.get("subType", None))
        #     )
        #     self.organizations[organization["organizationId"]] = Organization(
        #         botengine, organization["organizationId"], sub_type=organization.get("subType", None)
        #     )

        # # Remove any deleted sub organizations
        # for organization_id in copy.copy(self.organizations):
        #     if organization_id == botengine.get_organization_id():
        #         continue
        #     found = False
        #     for organization_access in botengine.get_organizations():
        #         organization = organization_access["organization"]
        #         if organization["organizationId"] == organization_id:
        #             found = True
        #             break
        #     if not found:
        #         botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
        #             f"|track_new_and_deleted_organizations() {organization_id} Not provided in organizations, deleting..."
        #         )
        #         self.delete_organization(botengine, organization_id)

        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            "<track_new_and_deleted_organizations()"
        )

    def async_data_request_ready(self, botengine, reference, content):
        """
        A botengine.request_data() request is ready
        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param content: Content of the data request

        """
        for organization_id in self.organizations:
            self.organizations[organization_id].async_data_request_ready(
                botengine, reference, content
            )

    def file_uploaded(self, botengine, device_object, file):
        """
        File was uploaded
        :param botengine: BotEngine environment
        :param device_object: Device object that uploaded the file
        :param file: File JSON structure
        """
        pass

    def sync_datastreams(self, botengine, address, content):
        """
        Synchronize the data stream messages across all organization objects
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Data Stream content
        """
        for organization_id in self.organizations:
            self.organizations[organization_id].datastream_updated(
                botengine, address, content
            )

    def sync_question(self, botengine, question):
        """
        Synchronize an answered question
        :param botengine: BotEngine environment
        :param question: Answered question
        """
        # Sync organization intelligence
        for organization_id in self.organizations:
            self.organizations[organization_id].question_answered(botengine, question)

    def sync_messages(self, botengine, messages):
        """
        Synchronize updated messages
        :param botengine: BotEngine environment
        :param messages: List of changed messages
        """
        pass

    def sync_documents(self, botengine, document, request_id):
        """
        Synchronize updated documents
        :param botengine: BotEngine environment
        :param document: Changed document
        :param request_id: Request ID for this document change
        """
        for organization_id in self.organizations:
            self.organizations[organization_id].document_updated(
                botengine, document, request_id
            )

    def run_organization_intelligence(self, botengine, intelligence_id, argument):
        """
        Because we don't know what organization_id owns this intelligence module, we have to own the responsibility of discovering the intelligence module here.
        :param botengine: BotEngine environment
        :param intelligence_id: ID of the intelligence module which needs its timer fired
        :param argument: Argument to pass into the timer_fired() method of the intelligence module
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">run_organization_intelligence() Organization Intelligence Timer Fired: "
            + str(intelligence_id)
        )
        for organization_id in self.organizations:
            self.organizations[organization_id].timer_fired(
                botengine, intelligence_id, argument
            )
            return

    def run_intelligence_schedules(self, botengine, schedule_id):
        """
        Notify each organization that the schedule fired.
        The organization should be responsible for telling all device and location intelligence modules,
        and performing periodic tasks like garbage collection.
        :param botengine: BotEngine environment
        """
        for organization_id in self.organizations:
            self.organizations[organization_id].schedule_fired(botengine, schedule_id)

    def delete_organization(self, botengine, organization_id):
        """
        Delete the given organization ID
        :param organization_id: Organization ID to delete
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">delete_organization() Deleting Organization: " + str(organization_id)
        )
        if organization_id in self.organizations.keys():
            del self.organizations[organization_id]

    def new_version(self, botengine):
        """
        New bot version detected
        :param botengine: BotEngine environment
        """
        for organization_id in self.organizations:
            self.organizations[organization_id].new_version(botengine)

    def is_version_updated(self, botengine):
        """
        Check if we are indeed running a new version of the bot.
        :param botengine: BotEngine environment
        :return: True if a new version was detected.
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            ">is_version_updated()"
        )
        import json
        import os

        with open(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "runtime.json")
        ) as f:
            j = json.load(f)
            version = j["version"]["version"]
            if not hasattr(self, "version") or version != self.version:
                botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                    "<is_version_updated() New version detected {} >> {}".format(
                        self.version if hasattr(self, "version") else "null", version
                    )
                )
                return True
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            "<is_version_updated()"
        )

        if botengine.local and botengine.local_execution_count == 0:
            botengine.local_execution_count += 1
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "<is_version_updated() Local execution new version detected {} >> {}".format(
                    self.version if hasattr(self, "version") else "null", version
                )
            )
            return True

        return False

    def update_version(self, botengine):
        """
        Trigger the new_version() if we are indeed running a new version of the bot.
        :param botengine: BotEngine environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">update_version()"
        )
        import json
        import os

        with open(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "runtime.json")
        ) as f:
            j = json.load(f)
            version = j["version"]["version"]

            self.version = version

        # Notify all locations
        self.new_version(botengine)
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<update_version()"
        )
