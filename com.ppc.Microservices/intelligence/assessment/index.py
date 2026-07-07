MICROSERVICES = {
    "DEVICE_MICROSERVICES": {
        # GripAble Assessment Device
        2009: [
            {
                "module": "intelligence.assessment.device_assessment_trends_microservice",
                "class": "DeviceAssessmentTrendsMicroservice",
            }
        ]
    },
    "LOCATION_MICROSERVICES": [
        {
            "module": "intelligence.assessment.location_assessment_microservice",
            "class": "LocationAssessmentMicroservice",
        }
    ],
}
