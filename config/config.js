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

// const localCompliments = require("./compliments.json")
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
    module: "MMM-WeatherEffects",
			position: "fullscreen_above",
    config: {
        rainConfig: {
            dropletCount: 30
        },
        snowConfig: {
            flakeCount: 15,
            sparkleEnabled: false,
            maxSize: 1.2
        }
    }
},
		{
			module: "alert",
			disabled: true,
			position: "top_bar"
		},
		{
			module: "updatenotification",
			disable: true,
			position: "top_bar"
		},
		{
			module: "clock",
			position: "top_left"
		},
		/* default/calendar module configuration */
		{
  			module: "calendar",
  			// hidden: true,
			position: "top_left",
  			config: {
    					broadcastPastEvents: true, // <= IMPORTANT to see past events
    					coloredText: true,
    					coloredSymbol: true,
    					calendars: [
      							{
        							url: "webcal://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics",
        							name: "us_holiday",
        							color: "red" 
							},
							{	url: "https://calendar.google.com/calendar/ical/mutkcai83gusm8ek7o6nj00cr4%40group.calendar.google.com/public/basic.ics",
								name: "burke_calendar",
								color: "#1e90ff"
							}
					],
				customEvents: [
      {
        keyword: "Mom|Lauren",
        symbol: "ice-cream",  // use a sunflower icon (FontAwesome or equivalent)
        color: "yellow"
      },
      {
        keyword: "Ben|Dad",
        symbol: "person-running",
        color: "#3BEBE5"
      },
      {
        keyword: "Cora",
        symbol: "wand-sparkles",
        color: "#D569FF"
      },
	  {
		keyword: "Church|Temple",
		symbol: "place-of-worship",
		color: "darkblue",
	  },
	  {
		keyword: "Jack",
		symbol: "user-ninja",
		color: "#F03535",
	  },
	{
		keyword: "Jane",
		symbol: "fort-awesome",
		color: "pink"
	},
	{
		keyword: "Cole",
		symbol: "space-awesome",
		color: "green"
	},				
	{ keyword: "Job",
	 symbol: "hand-sparkles",
	 color: "#EBE6E6"},
						
				]
			}
      		},
		// {
		//   module: "MMM-CalendarExt3",
		//   header: "Home Calendar",
		//   position: "upper_third",
		//   config: {
		//     locale: "en-US",
		//     title: "Burke Home Calendar",
		//     instanceId: "basicCalendar",
		//     useMarquee: false,
		//     calendarSet: ["burke_calendar", "us_holiday"],
		//     views: [
		//       {
		//         name: "homeView",
		//         mode: "week",
		//         maxEventLines: 5,
		//         firstDayOfWeek: 0,
		//         weeksInView: 2,
		// 	  	slotHeight: 60,
		//         weekIndex: 0,
		//         customLayout: {
		//           event: "{TIME} <br><span style='font-size: 0.9em;'>{TITLE}</span>"
		//         }
		//       }
		//     ],
		//     defaultView: "homeView"
		//   }
		// },
		{
  			module: "compliments",
			position: "middle_center",
			config: {
				updateInterval: 30000,
			    compliments: {
								"* * 10 1  *": ["Happy Birthday Jack!"],
								"* * 29 1  *": ["Happy Birthday Dad!"],
								"* * 4  3   *": ["Happy Birthday Cole!"],
								"* * 8  5   *": ["Happy Birthday Mommy!"],
								"* * 20 10 *": ["Happy Birthday Cora!"],
								"* * 26 11 *": ["Happy Birthday Jane!"],
								"* * 8  1  *": ["Happy Birthday Bret"],
								"* * 31 10 *": ["Boo!!"],
								"* * 25 12 *": ["Merry Christmas\n-❤ Santa"],
								"* * 6  7  *": ["Happy Anniversary!"],

								"anytime": [
									"You can do all things through Christ.",
									"Focus on the Temple"
								],
								"morning": [
									"Good morning!",
									"You look rested!",
									"Today is full of possibilities."
								],
								"afternoon": [
									"You must be the change you wish to see in the world.",
									"You don't have to be big to be brave.",
									"The happiness of your life depends upon the quality of your thoughts.",
									"The more that you read, the more things you will know. The more that you learn, the more places you'll go.",
									"Be yourself; everyone else is already taken.",
									"Kindness is the language which the deaf can hear and the blind can see.",
									"Nothing worthwhile is ever easy, but it's always worthwhile."
								],
								"evening": [
									"You made it through the day.",
									"Time to relax.",
									"You deserve some rest."
								],
								"weather:clear": [
									"What a beautiful day!",
									"Don't forget your sunglasses!",
									"Soak up that sun!"
								],
								"weather:rain": [
									"Stay dry out there!",
									"Perfect weather for a warm drink.",
									"Rainy days are good for reflection."
								],
								"weather:snow": [
									"It's a winter wonderland!",
									"Hope you're bundled up!",
									"Snowball fight, anyone?"
								],
								"weather:cloudy": [
									"The clouds can't hide your shine.",
									"A calm, cloudy day.",
									"Great weather for thinking deep thoughts."
								],
								"weather:thunderstorm": [
									"Hope you're safe and cozy!",
									"Let the thunder roll — you've got this.",
									"Maybe light a candle and chill?"
								]
							},
				fadeSpeed: 1000
			}
		},
		// {       module:"MMM-PregnancyTracker",
		// 	position: "bottom_left",
		// 	config: {
		// 		conceptionDate:"2025-04-21",
		// 		showDevelopmentalMilestones: false
		// 		}
		// },
		{
			module: "MMM-ImagesPhotos",
			position: "bottom_left",
			config: {
				opacity: 0.9,
				animationSpeed: 500,
				updateInterval: 60000,
				maxHeight: "50%",
				maxWidth:"50%",
				sequential: false  // process the image list randomly
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
			position: "top_right",
			// hidden: true,
			header: "Waxhaw Forecast",
                        config: {
				weatherProvider: "openmeteo",
				type: "forecast",
				lat: 34.9203813,
				lon: -80.6708347
			}
		},
		{
			module: "MMM-ThemeParkWaitTimes",
			header: "Magic Kingdom",
			position: "bottom_right",
			config: {
				futureHours: false,
				park: {
					entity: "75ea578a-adc8-4116-a54d-dccb60765ef9", // Magic Kingdom Park
					rides: [
						"796b0a25-c51e-456e-9bb8-50a324e301b3", // Jungle Cruise
						"2551a77d-023f-4ab1-9a19-8afec0190f39", // Haunted Mansion
						"5a43d1a7-ad53-4d25-abfe-25625f0da304", // TRON Lightcycle / Run
						"e8f0b426-7645-4ea3-8b41-b94ae7091a41", // Monsters, Inc. Laugh Floor
						"352feb94-e52e-45eb-9c92-e4b44c6b1a9d", // Pirates of the Caribbean
						"9d4d5229-7142-44b6-b4fb-528920969a2c", // Seven Dwarfs Mine Train
						"73cb9445-0695-47a3-87ce-d08ae36b5f3c", // Tiana's Bayou Adventure
						// "8183f3f2-1b59-4b9c-b634-6a863bdf8d84", // Walt Disney's Carousel of Progress
						"72c7343a-f7fb-4f66-95df-c91016de7338", // Buzz Lightyear’s Space Ranger Spin
						"b2260923-9315-40fd-9c6b-44dd811dbe64", // Space Mountain
						"ffcfeaa2-1416-4920-a1ed-543c1a1695c4", // Tomorrowland Transit Authority PeopleMover
						]
				}
			}
		},
		{
			module: "MMM-ThemeParkWaitTimes",
			header: "Hollywood Studios",
			position: "bottom_right",
			config: {
				futureHours: false,
				park: {
					entity: "288747d1-8b4f-4a64-867e-ea7c9b27bad8", // Disney's Hollywood Studios
					rides: [
						"6e118e37-5002-408d-9d88-0b5d9cdb5d14", // Mickey & Minnie's Runaway Railway
						"1a2e70d9-50d5-4140-b69e-799e950f7d18", // Star Wars: Rise of the Resistance
						"399aa0a1-98e2-4d2b-b297-2b451e9665e1", // Slinky Dog Dash
						"6f6998e8-a629-412c-b964-2cb06af8e26b", // The Twilight Zone Tower of Terror
						"20b5daa8-e1ea-436f-830c-2d7d18d929b5", // Toy Story Mania!
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
					},
					{
						title: "Disney Food Blog",
						url: "https://feeds.feedburner.com/disneyfoodblog/feed"
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
