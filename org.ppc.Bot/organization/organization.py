'''
Created on June 28, 2016

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import index
import importlib


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
        self.microservices = {}
        
    def initialize(self, botengine):
        """
        Initialize all services
        :param botengine:
        """
        # Synchronize info
        org = botengine.inputs['organization']
        self.organization_domain_name = org['domainName']
        self.organization_descriptive_name = org['organizationName']

        # Synchronize intelligence capabilities
        if len(self.microservices) != len(index.MICROSERVICES.get('ORGANIZATION_MICROSERVICES', [])):
            
            # Add more microservices
            for microservice_info in index.MICROSERVICES.get('ORGANIZATION_MICROSERVICES', []):
                if microservice_info['module'] not in self.microservices:
                    try:
                        microservice = importlib.import_module(microservice_info['module'])
                        class_ = getattr(microservice, microservice_info['class'])
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|initialize() Adding organization microservice: " + str(microservice_info['module']))
                        intelligence_object = class_(botengine, self)
                        self.microservices[microservice_info['module']] = intelligence_object

                    except Exception as e:
                        import traceback
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").error("|initialize() Could not add organization microservice: microservice={} error={} traceback={}".format(str(microservice_info['module']), str(e), str(traceback.format_exc())))
                        
                    
            # Remove microservices that no longer exist
            for module_name in self.microservices.keys():
                found = False
                for microservice_info in index.MICROSERVICES.get('ORGANIZATION_MICROSERVICES', []):
                    if microservice_info['module'] == module_name:
                        found = True
                        break
                    
                if not found:
                    botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|initialize() Deleting organization microservice: " + str(module_name))
                    del self.microservices[module_name]
        
        # Order intelligence modules alphabetically then by execution priority
        self.microservices = dict(sorted(self.microservices.items(), key=lambda module: module[0]))
        execution_priorities = {}
        for intelligence_info in index.MICROSERVICES.get('ORGANIZATION_MICROSERVICES', []):
            execution_priorities[intelligence_info['module']] = intelligence_info.get('execution_priority', 0)
        
        self.microservices = dict(sorted(self.microservices.items(), key=lambda module: execution_priorities.get(module[0], 0), reverse=True))
                    
        # Location intelligence execution
        for i in self.microservices:
            self.microservices[i].parent = self
            self.microservices[i].initialize(botengine)
        

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
        """
        for intelligence_id in self.microservices:
            self.microservices[intelligence_id].question_answered(botengine, question)

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Updated
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Data Stream content
        """
        for intelligence_id in self.microservices:
            try:
                self.microservices[intelligence_id].datastream_updated(botengine, address, content)
            except Exception as e:
                import traceback
                botengine.get_logger(f"{__name__}.{__class__.__name__}").warn("|datastream_updated() Error delivering datastream message to organization microservice (continuing execution): error={} traceback={}".format(str(e), str(traceback.format_exc())))

    def async_data_request_ready(self, botengine, reference, data_dict):
        """
        A botengine.request_data() asynchronous request for CSV data is ready.
        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param device_csv_dict: { 'device_id': 'csv data string' }
        """
        # Location microservices
        for microservice_id in self.microservices:
            if not hasattr(self.microservices[microservice_id], 'async_data_request_ready'):
                continue
            try:
                self.microservices[microservice_id].async_data_request_ready(botengine, reference, data_dict)
            except Exception as e:
                import traceback
                botengine.get_logger(f"{__name__}.{__class__.__name__}").warning("|async_data_request_ready() Error delivering async_data_request_ready to microservice: error={} traceback={}".format(str(e), str(traceback.format_exc())))
            
    def schedule_fired(self, botengine, schedule_id):
        """
        Schedule Fired.
        It is this location's responsibility to notify all microservices
        :param botengine: BotEngine environment
        """
        # Location intelligence modules
        for intelligence_id in self.microservices:
            self.microservices[intelligence_id].schedule_fired(botengine, schedule_id)
        
    def timer_fired(self, botengine, intelligence_id, argument):
        """
        Timer fired
        :param botengine: BotEngine environment
        :param intelligence_id: Microservice ID that fired
        :param argument: Optional argument
        """
        for microservice_id in self.microservices:
            if intelligence_id == self.microservices[microservice_id].intelligence_id:
                self.microservices[microservice_id].timer_fired(botengine, argument)
                return
    
    def document_updated(self, botengine, document, request_id):
        """
        Document Updated
        :param botengine: BotEngine environment
        :param document: Updated document
        :param requestId: Current request ID
        """
        for intelligence_id in self.microservices:
            if not hasattr(self.microservices[intelligence_id], 'document_updated'):
                continue
            self.microservices[intelligence_id].document_updated(botengine, document, request_id)

    #===========================================================================
    # Data Stream Message delivery
    #===========================================================================
    def distribute_datastream_message(self, botengine, address, content, internal=True, external=True):
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


    #===========================================================================
    # Narration
    #===========================================================================
    # def narrate(self, botengine, title, description, priority, icon, timestamp_ms=None, file_ids=None, extra_json_dict=None, update_narrative_id=None, update_narrative_timestamp=None, admin=False):
    #     """
    #     Narrate some activity
    #     :param botengine: BotEngine environment
    #     :param title: Title of the event
    #     :param description: Description of the event
    #     :param priority: 0=debug; 1=info; 2=warning; 3=critical
    #     :param icon: Icon name, like 'motion' or 'phone-alert'. See http://peoplepowerco.com/icons
    #     :param timestamp_ms: Optional timestamp for this event. Can be in the future. If not set, the current timestamp is used.
    #     :param file_ids: List of file ID's (media) to reference and show as part of the record in the UI
    #     :param extra_json_dict: Any extra JSON dictionary content we want to communicate with the UI
    #     :param update_narrative_id: Specify a narrative ID to update an existing record.
    #     :param update_narrative_timestamp: Specify a narrative timestamp to update an existing record. This is a double-check to make sure we're not overwriting the wrong record.
    #     :param admin:
    #     :return: { "narrativeId": id, "narrativeTime": timestamp_ms } if successful, otherwise None.
    #     """
    #     return botengine.narrate(self.location_id, title, description, priority, icon, timestamp_ms=timestamp_ms, file_ids=file_ids, extra_json_dict=extra_json_dict, update_narrative_id=update_narrative_id, update_narrative_timestamp=update_narrative_timestamp, admin=admin)
    #
    # def track(self, botengine, identifier, properties=None):
    #     """
    #     Track analytics
    #     :param botengine: BotEngine environment
    #     :param identifier: Unique identifier for this analytic
    #     :param properties: JSON dictionary of properties
    #     :return: { "narrativeId": id, "narrativeTime": timestamp_ms } if successful, otherwise None.
    #     """
    #     return self.narrate(botengine,
    #                  title=identifier,
    #                  description=None,
    #                  priority=botengine.NARRATIVE_PRIORITY_DETAIL,
    #                  icon=None,
    #                  extra_json_dict=properties,
    #                  admin=True)
    #
    # def delete_narration(self, botengine, narrative_id, narrative_timestamp):
    #     """
    #     Delete a narrative record
    #     :param botengine: BotEngine environment
    #     :param narrative_id: ID of the record to delete
    #     :param narrative_timestamp: Timestamp of the record to delete
    #     """
    #     botengine.delete_narration(self.location_id, narrative_id, narrative_timestamp)

