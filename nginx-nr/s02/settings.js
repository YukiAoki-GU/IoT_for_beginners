module.exports = {
    flowFile: "flows.json",
    credentialSecret: false,
    flowFilePretty: true,
    adminAuth: {
        type: "credentials",
        users: [{
            username: "s02",
            password: "$2b$08$57pTH/s8RWQ0YCE6GZnt6OafRnslGgP/zWmbELp6gE2NRC.O4oweC",
            permissions: "*"
        }]
    },

    uiPort: process.env.PORT || 1002,

     logging: {
         /** Only console logging is currently supported */
         console: {
             level: "info",
             metrics: false,
             audit: false
         }
     },

     exportGlobalContextKeys: false,
     externalModules: {
     },
    editorTheme: {
        palette: {
        },
        projects: {
            /** To enable the Projects feature, set this value to true */
            enabled: false,
            workflow: {
                mode: "manual"
            }
        },
        codeEditor: {
            lib: "ace",
            options: {
                theme: "vs",
            }
        }
    },

    functionExternalModules: true,
    functionGlobalContext: {
        // os:require('os'),
    },
    debugMaxLength: 1000,
    mqttReconnectTime: 15000,
    serialReconnectTime: 15000,
}
       
