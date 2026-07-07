MICROSERVICES = {

    # Map locations to their microservices
    "ORGANIZATION_MICROSERVICES": [
        # An organization is a set of locations. This is a list of microservices to add to your organization,
        # which listens to and coordinates locations across your entire organization. Organization microservices trigger
        # off of all data inputs.

        {"module": "intelligence.billing_per_sub.organization_billing_microservice", "class": "OrganizationBillingMicroservice"}
    ]
}
