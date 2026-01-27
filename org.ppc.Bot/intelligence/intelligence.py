'''
Created on March 27, 2019

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import bot

class Intelligence:
    """
    Base Intelligence Module Class / Interface for Organizations
    """
    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, like an Organization
        """
        import uuid
        self.intelligence_id = str(uuid.uuid4())
        self.parent = parent
        
    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return
    
    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        return

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
        """
        return
    
    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)
    
    def schedule_fired(self, botengine, schedule_id):
        """
        The bot executed on a hard coded schedule specified by our runtime.json file
        :param botengine: BotEngine environment
        :param schedule_id: Schedule ID that is executing from our list of runtime schedules
        """
        return
        
    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        return

    def async_data_request_ready(self, botengine, reference, content):
        """
        A botengine.request_data() asynchronous request for CSV data is ready.

        This is part of a very scalable method to extract large amounts of data from the server for the purpose of
        machine learning services. If a service needs to extract a large amount of data for one or multiple devices,
        the developer should call botengine.request_data(..) and also allow the bot to trigger off of trigger type 2048.
        The bot can exit its current execution. The server will independently gather all the necessary data and
        capture it into a LZ4-compressed CSV file on the server which is available for one day and accessible only by
        the bot through a public HTTPS URL identified by a cryptographic token. The bot then gets triggered and
        downloads the CSV data, passing the data throughout the environment with this async_data_request_ready()
        event-driven method.

        IMPORTANT: This method executes in an asynchronous environment where you are NOT allowed to:
        - Set timers or alarms
        - Manage class variables that persist across executions
        - Perform other stateful operations

        To return to a synchronous environment where you can use timers and manage state, call:
        botengine.async_execute_again_in_n_seconds(seconds)

        Developers are encouraged to use the 'reference' argument inside calls to botengine.request_data(..). The
        reference is passed back out at the completion of the request, allowing the developer to ensure the
        data request that is now available was truly destined for their microservice.

        Your bots will need to include the following configuration for data requests to operate:
        * runtime.json should include trigger 2048
        * structure.json should include inside 'pip_install_remotely' a reference to the "lz4" Python package

        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param content: Data request content
        """
        # For backwards compatibility, call the deprecated data_request_ready method if it exists
        if hasattr(self, 'data_request_ready'):
            return self.data_request_ready(botengine, reference, content)
        return

    # ===============================================================================
    # DEPRECATED METHODS - DO NOT USE IN NEW CODE
    # ===============================================================================
    
    def data_request_ready(self, botengine, reference, content):
        """
        DEPRECATED: Use async_data_request_ready() instead.
        
        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param content: Data request content
        """
        return

    def document_updated(self, botengine, document, request_id):
        """
        Document and/or questions and answers were updated from the document processing service
        :param botengine: BotEngine environment
        :param document: Updated document
        :param request_id: Request ID
        """
        pass

    def get_document_property_updates(self, botengine):
        """
        Return document property updates
        Example:
        {
            "documentId": 0,
            "properties": [{
                "name": "processed",
                "value": "1"
            }]
        }
        :param botengine: BotEngine environment
        :return: Documents property updates
        """
        if not hasattr(self, "document_property_updates"):
            return None
        return self.document_property_updates
    
    def get_documents_questions(self, botengine):
        """
        Return a list of documents questions
        Example: 
        [
            {
                "documentId": 0,
                "questions": ["What is this?"],
                "questionKeys": ["summary"]
            }
        ]
        :param botengine: BotEngine environment
        :return: List of documents questions
        """
        if not hasattr(self, "documents_questions"):
            return None
        return self.documents_questions

    #===============================================================================
    # Built-in Timer and Alarm methods.
    #===============================================================================
    def start_timer_ms(self, botengine, milliseconds, argument=None, reference=""):
        """
        Start a relative timer in milliseconds
        :param botengine: BotEngine environment
        :param seconds: Time in milliseconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        # We seed the reference with this intelligence ID to make it unique against all other intelligence modules.
        bot.start_organization_intelligence_timer_ms(botengine, milliseconds, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def start_timer_s(self, botengine, seconds, argument=None, reference=""):
        """
        Helper function with an explicit "_s" at the end, to start a timer in seconds
        :param botengine: BotEngine environment
        :param seconds: Time in seconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        self.start_timer(botengine, seconds, argument, str(reference))

    def start_timer(self, botengine, seconds, argument=None, reference=""):
        """
        Start a relative timer in seconds
        :param botengine: BotEngine environment
        :param seconds: Time in seconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        bot.start_organization_intelligence_timer(botengine, seconds, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def is_timer_running(self, botengine, reference=""):
        """
        Check if a timer or alarm with the given reference is running
        :param botengine: BotEngine environment
        :param reference: Reference
        :return: True if timers or alarms with the given reference are running.
        """
        return botengine.is_timer_running(self.intelligence_id + str(reference))

    def cancel_timers(self, botengine, reference=""):
        """
        Cancel timers with the given reference
        :param botengine: BotEngine environment
        :param reference: Cancel all timers with the given reference
        """
        botengine.cancel_timers(self.intelligence_id + str(reference))
    
    def set_alarm(self, botengine, timestamp_ms, argument=None, reference=""):
        """
        Set an absolute alarm
        :param botengine: BotEngine environment
        :param timestamp_ms: Absolute time in milliseconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        # We seed the reference with this intelligence ID to make it unique against all other intelligence modules.
        bot.set_organization_intelligence_alarm(botengine, timestamp_ms, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def is_alarm_running(self, botengine, reference=""):
        """
        Check if a timer or alarm with the given reference is running
        :param botengine: BotEngine environment
        :param reference: Reference
        :return: True if timers or alarms with the given reference are running.
        """
        return botengine.is_timer_running(self.intelligence_id + str(reference))

    def cancel_alarms(self, botengine, reference=""):
        """
        Cancel alarms with the given reference
        :param botengine: BotEngine environment
        :param reference: Cancel all alarms with the given reference
        """
        # It's not a mistake that this is forwarding to `cancel_timers`.
        # They're all the same thing underneath, and this is a convenience method help to avoid confusion and questions.
        botengine.cancel_timers(self.intelligence_id + str(reference))
