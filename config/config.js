/* Config Sample
 *
 * For more information on how you can configure this file
 * see https://docs.magicmirror.builders/configuration/introduction.html
 * and https://docs.magicmirror.builders/modules/configuration.html
 *
 * You can use environment variables using a `config.js.template` file instead of `config.js`
 * which will be converted to `config.js` while starting. For more information
 * see https://docs.magicmirror.builders/configuration/introduction.html#enviromnent-variables
 */
let config = {
	address: "localhost",	// Address to listen on, can be:
							// - "localhost", "127.0.0.1", "::1" to listen on loopback interface
							// - another specific IPv4/6 to listen on a specific interface
							// - "0.0.0.0", "::" to listen on any interface
							// Default, when address config is left out or empty, is "localhost"
	port: 8080,
	basePath: "/",	// The URL path where MagicMirror² is hosted. If you are using a Reverse proxy
									// you must set the sub path here. basePath must end with a /
	ipWhitelist: ["127.0.0.1", "::ffff:127.0.0.1", "::1"],	// Set [] to allow all IP addresses
									// or add a specific IPv4 of 192.168.1.5 :
									// ["127.0.0.1", "::ffff:127.0.0.1", "::1", "::ffff:192.168.1.5"],
									// or IPv4 range of 192.168.3.0 --> 192.168.3.15 use CIDR format :
									// ["127.0.0.1", "::ffff:127.0.0.1", "::1", "::ffff:192.168.3.0/28"],

	useHttps: false,			// Support HTTPS or not, default "false" will use HTTP
	httpsPrivateKey: "",	// HTTPS private key path, only require when useHttps is true
	httpsCertificate: "",	// HTTPS Certificate path, only require when useHttps is true

	language: "en",
	locale: "en-US",   // this variable is provided as a consistent location
			   // it is currently only used by 3rd party modules. no MagicMirror code uses this value
			   // as we have no usage, we  have no constraints on what this field holds
			   // see https://en.wikipedia.org/wiki/Locale_(computer_software) for the possibilities

	logLevel: ["INFO", "DEBUG", "LOG", "WARN", "ERROR"], // Add "DEBUG" for even more logging
	timeFormat: 12,
	units: "imperial",

	modules: [
		{
			module: "alert",
		},
		{
			module: "updatenotification",
			position: "top_bar"
		},
		{
			module: "clock",
			position: "top_left"
		},
		/* default/calendar module configuration */
		{
  			module: "calendar",
  			hidden: true,
  			config: {
    					broadcastPastEvents: true, // <= IMPORTANT to see past events
    					calendars: [
      							{
        							url: "webcal://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics",
        							name: "us_holiday",
        							color: "red" 
							},
							{	url: "https://calendar.google.com/calendar/ical/mutkcai83gusm8ek7o6nj00cr4%40group.calendar.google.com/public/basic.ics",
								name: "burke_calendar",
								color: "blue"
							}
					]
			}
      		},
		{
 			module: "MMM-CalendarExt3",
			header: "Home Calendar",
  			position: "upper_third",
  			config: {
	    			locale: "en-US",
					title: "Burke Home Calendar",
					mode: "week",
					useMarquee: true,
					instanceId: "basicCalendar",
					maxEventLines: 5,
					firstDayOfWeek: 0,
					weeksInView: 2,
					weekIndex: 0,
    					calendarSet: ["burke_calendar","us_holiday"]
  			}
		},
		{
  			module: "compliments",
			position: "middle_center",
			config: {
				updateInterval: 30000,
			    remoteFile: "https://raw.githubusercontent.com/BenLBurke/mirror/refs/heads/master/config/compliments.json", // Looks in ~/MagicMirror/config/
			    fadeSpeed: 1000
			}
		},
		{       module:"MMM-PregnancyTracker",
			position: "bottom_left",
			config: {
				conceptionDate:"2025-04-21",
				showDevelopmentalMilestones: false
				}
		},
		{
			module: "weather",
			position: "top_right",
                        header: "Waxhaw Weather",
			config: {
				weatherProvider: "openmeteo",
				type: "current",
				lat: 34.9203813,
				lon: -80.6708347
			}
		},
		{
			module: "weather",
			hidden: true,
			header: "Waxhaw Forecast",
                        config: {
				weatherProvider: "openmeteo",
				type: "forecast",
				lat: 34.9203813,
				lon: -80.6708347
			}
		},
		{ 	
			module: "MMM-DisneyWaitTimes",
			header: "Magic Kingdom",
			position: "bottom_right",
			config: { 
				park: {
					name: "Magic Kingdom - Walt Disney World",
					rides: [
						"Haunted Mansion",
						"Walt Disney's Carousel of Progress",
						"Monster's Inc. Laugh Floor",
						"Jungle Cruise",
						"TRON Lightcycle / Run"
						]
				}
			}
		},
		{
			module: "MMM-DisneyWaitTimes",
			header: "Animal Kingdom",
			position: "bottom_right",
			config: {
				park: {
		
					name: "Animal Kingdom - Walt Disney World",
					rides: [
						"Expedition Everest - Legend of the Forbidden Mountain",
						"Kilimanjaro Safaris",
						"Avatar Flight of Passage"
					]
				}
			}
		},
		{	
			module: "MMM-DisneyWaitTimes",
			header: "Hollywood Studios",
			position: "bottom_right",
			config: {
				park: {
					name: "Hollywood Studios - Walt Disney World",
					rides: [
						"Star Wars: Rise of the Resistance",
						"Mickey & Minnie's Runaway Railway"
					]
				}
			}
		},
		{
			module: "newsfeed",
			position: "bottom_bar",
			config: {
				feeds: [
					{
						title: "Church News Room",
						url: "https://newsroom.churchofjesuschrist.org/blog/rss"
					}
				],
				showSourceTitle: true,
				showPublishDate: true,
				broadcastNewsFeeds: true,
				broadcastNewsUpdates: true
			}
		},
	]
};

/*************** DO NOT EDIT THE LINE BELOW ***************/
if (typeof module !== "undefined") { module.exports = config; }
