'''
Created on March 27, 2017

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import json

import localization

from organization.organization import Organization
import utilities.utilities as utilities

def run(botengine):
    """
    Entry point for bot microservices
    :param botengine: BotEngine environment object, our window to the outside world.
    """
    localization.initialize(botengine)

    #===========================================================================
    # print("INPUTS: " + json.dumps(botengine.get_inputs(), indent=2, sort_keys=True))
    #===========================================================================
    trigger_type = botengine.get_trigger_type()
    triggers = botengine.get_triggers()
    botengine.get_logger(f"{__name__}").info(">run() trigger_type=" + str(trigger_type))
    
    # Grab our non-volatile memory
    organization = load_organization(botengine)

    # DISCUSSION: The location bot has improved logic to gracefully start the bot up and
    # load microservices.  This class could also include this logic if needed.
    # See com.ppc.Bot/bot.py

    executed = False

    # UNPAUSED
    if trigger_type == botengine.TRIGGER_UNPAUSED:
        executed = True
        pass

    # SCHEDULE TRIGGER
    if trigger_type & botengine.TRIGGER_SCHEDULE != 0:
        executed = True
        schedule_id = "DEFAULT"
        if 'scheduleId' in botengine.get_inputs():
            schedule_id = botengine.get_inputs()['scheduleId']

        organization.schedule_fired(botengine, schedule_id)

    # QUESTIONS ANSWERED
    if trigger_type & botengine.TRIGGER_QUESTION_ANSWER != 0:
        executed = True
        question = botengine.get_answered_question()
        botengine.get_logger(f"{__name__}").info("|run() Answered: " + str(question.key_identifier))
        botengine.get_logger(f"{__name__}").info("|run() Answer = {}".format(question.answer))
        organization.question_answered(botengine, question)
        
    # DATA STREAM TRIGGERS
    if trigger_type & botengine.TRIGGER_DATA_STREAM != 0:
        executed = True
        data_stream = botengine.get_datastream_block()
        botengine.get_logger(f"{__name__}").info("|run() Data Stream: " + json.dumps(data_stream, sort_keys=True))
        if 'address' not in data_stream:
            botengine.get_logger(f"{__name__}").warn("|run() Data stream message does not contain an 'address' field. Ignoring the message.")
            
        else:
            address = data_stream['address']

            if 'feed' in data_stream:
                content = data_stream['feed']
            else:
                content = {}

            if 'fromAppInstanceId' in data_stream:
                if type(content) == type({}):
                    content['sender_bot_id'] = data_stream['fromAppInstanceId']

            organization.datastream_updated(botengine, address, content)

    # DATA REQUEST
    if trigger_type & botengine.TRIGGER_DATA_REQUEST != 0:
        executed = True
        botengine.get_logger(f"{__name__}").info("|run() Data request received")
        data = botengine.get_data_block()
        events = {}
        imported = False

        import importlib
        try:
            import lz4.block
            imported = True
        except ImportError:
            botengine.get_logger(f"{__name__}").error("|run() Attempted to import 'lz4' to uncompress the data request response, but lz4 is not available. Please add 'lz4' to 'pip_install_remotely' in your structure.json.")
            pass

        if imported:
            for d in data:
                reference = None
                if 'key' in d:
                    reference = d['key']

                if reference not in events:
                    events[reference] = {}

                botengine.get_logger(f"{__name__}").info("|run() Downloading {} bytes...".format(d['compressedLength']))
                r = botengine._requests.get(d['url'], timeout=60, stream=True)
                data = lz4.block.decompress(r.content, uncompressed_size=d['dataLength'])

                if d['type'] == botengine.DATA_REQUEST_TYPE_LOCATIONS:
                    headers_raw = data.decode('utf-8').split('\n')[0].strip().split(",")
                    headers = []
                    import re
                    for h in headers_raw:
                        # Transform CamelCase to snake_case
                        headers.append(re.sub(r'(?<!^)(?=[A-Z])', '_', h).lower())

                    data = data.decode('utf-8').split('\n')[1:]

                    # formated[location_id] = {'timezone': __, 'creation_time': __, 'event': __, 'organization_id': __, 'group_id': __}
                    formatted = {}

                    # Here we go line-by-line and transform CSV strings into a dictionary of headers : values.
                    for line in data:
                        if line != "":
                            l = line.strip().split(",")
                            processed = {}
                            for index, header in enumerate(headers):
                                processed[header] = utilities.normalize_measurement(l[index])

                            location_id = processed['id']
                            del processed['id']
                            formatted[location_id] = processed

                    events[reference] = formatted

                elif d['type'] == botengine.DATA_REQUEST_TYPE_DEVICES:
                    headers_raw = data.decode('utf-8').split('\n')[0].strip().split(",")
                    headers = []
                    import re
                    for h in headers_raw:
                        headers.append(re.sub(r'(?<!^)(?=[A-Z])', '_', h).lower())

                    data = data.decode('utf-8').split('\n')[1:]

                    botengine.get_logger(f"{__name__}").info("|run() HEADERS: {}".format(headers))

                    # formatted[location_id][device_id] = { ... }
                    formatted = {}

                    # Here we go line-by-line and transform CSV strings into a dictionary of headers : values.
                    for line in data:
                        if line != "":
                            l = line.strip().split(",")
                            processed = {}
                            for index, header in enumerate(headers):
                                processed[header] = utilities.normalize_measurement(l[index])

                            location_id = int(processed['location_id'])
                            del processed['location_id']

                            device_id = processed['device_id']
                            del processed['device_id']

                            formatted[location_id] = { device_id : processed }

                    events[reference] = formatted

                else:
                    events[reference] = data

            for reference in events:
                organization.async_data_request_ready(botengine, reference, events[reference])

        # DO NOT SAVE CORE VARIABLES HERE.
        botengine.get_logger(f"{__name__}").info("<run()")
        return

    # DOCUMENTS TRIGGER
    if botengine.get_bot_type() == botengine.BOT_TYPE_ORGANIZATION_RAG and trigger_type in [botengine.TRIGGER_UNPAUSED, botengine.TRIGGER_DOCUMENTS]:
    # if trigger_type & botengine.TRIGGER_DOCUMENTS != 0:
        executed = True
        request_id = botengine.get_documents_request_id()
        document = botengine.get_document_block()
        organization.document_updated(botengine, document, request_id)
    if not executed:
        botengine.get_logger(f"{__name__}").error("|run() Unknown trigger {}".format(trigger_type))
    
    # Always save your variables!
    botengine.save_variable("organization", organization, required_for_each_execution=True)
    botengine.get_logger(f"{__name__}").info("<run()")
    

    
def load_organization(botengine):
    """
    Load the organization object
    :param botengine: Execution environment
    """
    botengine.get_logger(f"{__name__}").info(">load_organization()")
    try:
        organization = botengine.load_variable("organization")
        botengine.get_logger(f"{__name__}").info("|load_organization() Loaded the organization")

    except:
        organization = None
        botengine.get_logger(f"{__name__}").info("|load_organization() Unable to load the organization")

    if organization == None:
        botengine.get_logger(f"{__name__}").info("|load_organization() Creating a new organization object. Hello.")
        organization_id = botengine.get_inputs()['organization']['organizationId']
        botengine.get_logger(f"{__name__}").info("|load_organization() Organization ID is {}.".format(organization_id))

        organization = Organization(botengine, organization_id)
        botengine.save_variable("organization", organization, required_for_each_execution=True)

        try:
            import signals.analytics as analytics
            analytics.track(botengine, organization, 'reset')

        except ImportError:
            pass

    organization.initialize(botengine)
    botengine.get_logger(f"{__name__}").info("<load_organization()")
    return organization

def get_document_property_updates(botengine):
    """
    Get the document updates provided by any specific microservice
    
    Example:
    {
      "documentId": 0,
      "properties": [
        {
          "name": "some",
          "value": "thing" # If empty remove this property
        }
      ]
    }

    :param botengine: BotEngine environment
    :return: Document
    
    """
    botengine.get_logger(f"{__name__}").debug(">get_documents_property_update()")
    organization = load_organization(botengine)
    
    document = {}
    
    # Extract document property updates from all microservices
    for microservice in organization.microservices.keys():
        document_property_updates = organization.microservices[microservice].get_document_property_updates(botengine)
        
        botengine.get_logger(f"{__name__}").debug("|get_document_property_updates() microservice: {} - {}".format(microservice, document_property_updates))

        _append_document_property_updates(botengine, document, document_property_updates)
    
    botengine.get_logger(f"{__name__}").info("|get_document_property_updates() Document: {}".format(document))
    botengine.get_logger(f"{__name__}").debug("<get_document_property_updates()")
    return document

def get_documents_questions(botengine):
    """
    Get the document questions provided by any specific microservice
    
    Example:
    [
      {
        "documentId": 0,
        "questions": [
          "What is this?"
        ],
        "questionKeys": [
          "summary"
        ]
      }
    ]

    :param botengine: BotEngine environment
    :return: List of documents
    
    """
    botengine.get_logger(f"{__name__}").debug(">get_documents_questions()")
    organization = load_organization(botengine)
    
    documents = []
    
    # Extract document questions from all microservices
    for microservice in organization.microservices.keys():
        documents_questions = organization.microservices[microservice].get_documents_questions(botengine)
        
        botengine.get_logger(f"{__name__}").debug("|get_documents_questions() microservice: {} - {}".format(microservice, documents_questions))

        _append_documents_questions(botengine, documents, documents_questions)
    
    botengine.get_logger(f"{__name__}").info("|get_documents_questions() Documents: {}".format(documents))
    botengine.get_logger(f"{__name__}").debug("<get_documents_questions()")
    return documents

def _append_document_property_updates(botengine, document, document_property_updates):
    """
    Append document property updates to the existing document updates
    :param botengine: BotEngine environment
    :param document: Existing document updates
    :param document_property_updates: New document updates
    """
    botengine.get_logger(f"{__name__}").info(">_append_document_property_updates()")
    botengine.get_logger(f"{__name__}").info("|_append_document_property_updates() document={}".format(document))
    botengine.get_logger(f"{__name__}").info("|_append_document_property_updates() document_property_updates={}".format(document_property_updates))
    if 'documentId' in document_property_updates:
        if document == {}:
            document['documentId'] = document_property_updates['documentId']
            document['properties'] = document_property_updates.get('properties', [])
            botengine.get_logger(f"{__name__}").info("|_append_document_property_updates() First update")
        else:
            botengine.get_logger(f"{__name__}").info("|_append_document_property_updates() Combine updates")
            document['properties'].extend(document_property_updates.get('properties', []))
    
    botengine.get_logger(f"{__name__}").info("<_append_document_property_updates() document={}".format(document))

def _append_documents_questions(botengine, documents, documents_questions):
    """
    Append document questions to the existing document updates
    :param botengine: BotEngine environment
    :param documents: Existing document updates
    :param documents_questions: New document updates
    """
    botengine.get_logger(f"{__name__}").debug(">_append_documents_questions()")
    for document_question in documents_questions:
        if 'output_schema' in document_question:
            document_question['outputSchema'] = document_question['output_schema']
            del document_question['output_schema']
    if len(documents) == 0:
        botengine.get_logger(f"{__name__}").debug("|_append_documents_questions() First update")
        documents.extend(documents_questions)
    else:
        botengine.get_logger(f"{__name__}").debug("|_append_documents_questions() Combine updates")
        for document_question in documents_questions:
            new_updates = any([existing_updates for existing_updates in documents if existing_updates["documentId"] != document_question["documentId"]])
            if new_updates:
                botengine.get_logger(f"{__name__}").debug("|_append_documents_questions() New document updates")
                documents.append(document_question)
            else:
                botengine.get_logger(f"{__name__}").debug("|_append_documents_questions() Existing document updates")
                existing_document_questions = [existing_updates for existing_updates in documents if existing_updates["documentId"] == document_question["documentId"]][0]
                for question in existing_document_questions["questions"]:
                    if any([question == document_question for document_question in document_question["questions"]]):
                        break
                    else:
                        existing_document_questions["questions"].extend([document_question for document_question in document_question["questions"]])
                for question_key in existing_document_questions.get("questionKeys", []):
                    if any([question_key == document_question for document_question in document_question.get("questionKeys", [])]):
                        break
                    else:
                        existing_document_questions["questionKeys"].extend([document_question for document_question in document_question.get("questionKeys", [])])
    
    botengine.get_logger(f"{__name__}").debug("<_append_documents_questions() documents={}".format(documents))

# ===============================================================================
# Organization Intelligence Timers
# ===============================================================================
def _organization_intelligence_fired(botengine, argument_tuple):
    """
    Entry point into this bot
    Location intelligence timer or alarm fired
    :param botengine: BotEngine Environment
    :param argument_tuple: (intelligence_id, argument)
    """
    botengine.get_logger(f"{__name__}").info(">_organization_intelligence_fired()")
    organization = load_organization(botengine)
    organization.timer_fired(botengine, argument_tuple[0], argument_tuple[1])
    botengine.save_variable("organization", organization, required_for_each_execution=True)
    botengine.get_logger(f"{__name__}").info("<_organization_intelligence_fired()")


def start_organization_intelligence_timer(botengine, seconds, intelligence_id, argument, reference):
    """
    Start a relative location intelligence timer
    :param botengine: BotEngine environment
    :param seconds: Seconds from the start of the current execution to make this timer fire
    :param intelligence_id: ID of the intelligence module to trigger when this timer fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(">start_organization_intelligence_timer()")
    botengine.get_logger(f"{__name__}").info("|start_organization_intelligence_timer() seconds={} reference={}".format(seconds, reference))
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.start_timer_s(int(seconds), _organization_intelligence_fired, (intelligence_id, argument), reference)
    botengine.get_logger(f"{__name__}").info("<start_organization_intelligence_timer()")


def start_organization_intelligence_timer_ms(botengine, milliseconds, intelligence_id, argument, reference):
    """
    Start a relative location intelligence timer
    :param botengine: BotEngine environment
    :param milliseconds: Milliseconds from the start of the current execution to make this timer fire
    :param intelligence_id: ID of the intelligence module to trigger when this timer fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(">start_organization_intelligence_timer_ms()")
    botengine.get_logger(f"{__name__}").info("|start_organization_intelligence_timer_ms() milliseconds={} reference={}".format(milliseconds, reference))
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.start_timer_ms(int(milliseconds), _organization_intelligence_fired, (intelligence_id, argument), reference)
    botengine.get_logger(f"{__name__}").info("<start_organization_intelligence_timer_ms()")


def set_organization_intelligence_alarm(botengine, timestamp_ms, intelligence_id, argument, reference):
    """
    Set an absolute location intelligence alarm
    :param botengine: BotEngine environment
    :param timestamp: Absolute timestamp in milliseconds at which to trigger this alarm
    :param intelligence_id: ID of the intelligence module to trigger when this alarm fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(">set_organization_intelligence_alarm()")
    botengine.get_logger(f"{__name__}").info("|set_organization_intelligence_alarm() timestamp_ms={} reference={}".format(timestamp_ms, reference))
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.set_alarm(int(timestamp_ms), _organization_intelligence_fired, (intelligence_id, argument), reference)
    botengine.get_logger(f"{__name__}").info("|set_organization_intelligence_alarm()")


def cancel_organization_intelligence_timers(botengine, reference):
    """
    Cancel all location intelligence timers and alarms with the given reference
    :param botengine: BotEngine environment
    :param reference: Unique reference name for which to cancel all timers and alarms
    """
    botengine.cancel_timers(reference)


def is_organization_timer_running(botengine, reference):
    """
    Determine if the timer with the given reference is running
    :param botengine: BotEngine environment
    :param reference: Unique reference name for the timer
    :return: True if the timer is running
    """
    return botengine.is_timer_running(reference)

