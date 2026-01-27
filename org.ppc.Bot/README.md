# FOUNDATIONAL BOT FOR ORGANIZATIONS

org.ppc.Bot is a foundational bot which you can extend and build upon in your own bots.

It provides the following features:

* Manages memory automatically. No need to save/load variables.
* Transforms the underlying infrastructure of bots into a nice event-driven framework.
* Allows developers to focus on creating event-driven microservices and behaviors instead of low-level code.
* Dynamically adds and removes microservices from live bot instances already running in peoples' accounts as new versions and updates of your bot are published.
* Multiplexes timers and alarms infinitely, and provides nice methods to start timers and set alarms.

*Do not try to commit this bot directly.*  This provides a foundation for you to rapidly build your own bot microservices.

To extend this bot foundation, apply the 'extends' attribute in your bot's structure.json file:

    'extends': 'org.ppc.Bot' 
    
When you --generate or --commit your bot, first all of the files from com.ppc.Bot will be copied into a new temporary directory, then all the files from your bot will be copied on top of that directory, allowing you to override and extend all the files in com.ppc.Bot. 

## Adding to an organization

1. As an administrator/developer, allow this bot to be purchased by an organization.

    botengine --add_organization org.ppc.MyBot --o 1234
    
2. Purchase the bot into the organization

    botengine --purchase org.ppc.MyBot -o 1234
    
3. Verify your purchase and obtain the instance ID

    botengine --my_purchased_bots -o 1234
    
    This will return an instance ID like 5555
    
4. Run the bot locally on behalf of the organization

    botengine --run org.ppc.MyBot -o 1234 -i 5555
    
    
