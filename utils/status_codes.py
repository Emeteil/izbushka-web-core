status_codes = {
    400: {
        "title": "400 Bad Request",
        "description": "The server cannot or will not process the request due to an apparent client error."
    },
    401: {
        "title": "401 Unauthorized",
        "description": "Authentication is required and has failed or has not yet been provided."
    },
    402: {
        "title": "402 Payment Required",
        "description": "Reserved for future use."
    },
    403: {
        "title": "403 Forbidden",
        "description": "The server understood the request but refuses to authorize it."
    },
    404: {
        "title": "404 Not Found",
        "description": "The requested resource could not be found but may be available in the future."
    },
    405: {
        "title": "405 Method Not Allowed",
        "description": "The request method is not supported by the resource."
    },
    406: {
        "title": "406 Not Acceptable",
        "description": "The requested resource is capable of generating only content not acceptable according to the Accept headers sent in the request."
    },
    407: {
        "title": "407 Proxy Authentication Required",
        "description": "The client must first authenticate itself with the proxy."
    },
    408: {
        "title": "408 Request Timeout",
        "description": "The server timed out waiting for the request."
    },
    409: {
        "title": "409 Conflict",
        "description": "The request could not be completed due to a conflict with the current state of the resource."
    },
    410: {
        "title": "410 Gone",
        "description": "The requested resource is no longer available and will not be available again."
    },
    411: {
        "title": "411 Length Required",
        "description": "The request did not specify the length of its content, which is required by the requested resource."
    },
    412: {
        "title": "412 Precondition Failed",
        "description": "The server does not meet one of the preconditions that the requester put on the request header fields."
    },
    413: {
        "title": "413 Payload Too Large",
        "description": "The request is larger than the server is willing or able to process."
    },
    414: {
        "title": "414 URI Too Long",
        "description": "The URI provided was too long for the server to process."
    },
    415: {
        "title": "415 Unsupported Media Type",
        "description": "The request entity has a media type which the server or resource does not support."
    },
    416: {
        "title": "416 Range Not Satisfiable",
        "description": "The client has asked for a portion of the file, but the server cannot supply that portion."
    },
    417: {
        "title": "417 Expectation Failed",
        "description": "The server cannot meet the requirements of the Expect request-header field."
    },
    418: {
        "title": "418 I'm a teapot",
        "description": "Any attempt to brew coffee with a teapot should result in the error code \"418 I'm a teapot\"."
    },
    421: {
        "title": "421 Misdirected Request",
        "description": "The request was directed at a server that is not able to produce a response."
    },
    422: {
        "title": "422 Unprocessable Entity",
        "description": "The request was well-formed but was unable to be followed due to semantic errors."
    },
    423: {
        "title": "423 Locked",
        "description": "The resource that is being accessed is locked."
    },
    424: {
        "title": "424 Failed Dependency",
        "description": "The request failed due to failure of a previous request."
    },
    425: {
        "title": "425 Too Early",
        "description": "Indicates that the server is unwilling to risk processing a request that might be replayed."
    },
    426: {
        "title": "426 Upgrade Required",
        "description": "The client should switch to a different protocol."
    },
    428: {
        "title": "428 Precondition Required",
        "description": "The origin server requires the request to be conditional."
    },
    429: {
        "title": "429 Too Many Requests",
        "description": "The user has sent too many requests in a given amount of time."
    },
    431: {
        "title": "431 Request Header Fields Too Large",
        "description": "The server is unwilling to process the request because either an individual header field, or all the header fields collectively, are too large."
    },
    451: {
        "title": "451 Unavailable For Legal Reasons",
        "description": "A server operator has received a legal demand to deny access to a resource or to a set of resources."
    },
    500: {
        "title": "500 Internal Server Error",
        "description": "The server encountered an unexpected condition that prevented it from fulfilling the request."
    },
    501: {
        "title": "501 Not Implemented",
        "description": "The server either does not recognize the request method, or it lacks the ability to fulfill the request."
    },
    502: {
        "title": "502 Bad Gateway",
        "description": "The server, while acting as a gateway or proxy, received an invalid response from an upstream server."
    },
    503: {
        "title": "503 Service Unavailable",
        "description": "The server is currently unable to handle the request due to a temporary overload or scheduled maintenance."
    },
    504: {
        "title": "504 Gateway Timeout",
        "description": "The server, while acting as a gateway or proxy, did not receive a timely response from an upstream server."
    },
    505: {
        "title": "505 HTTP Version Not Supported",
        "description": "The server does not support the HTTP protocol version used in the request."
    },
    506: {
        "title": "506 Variant Also Negotiates",
        "description": "Transparent content negotiation for the request results in a circular reference."
    },
    507: {
        "title": "507 Insufficient Storage",
        "description": "The server is unable to store the representation needed to complete the request."
    },
    508: {
        "title": "508 Loop Detected",
        "description": "The server detected an infinite loop while processing the request."
    },
    510: {
        "title": "510 Not Extended",
        "description": "Further extensions to the request are required for the server to fulfill it."
    },
    511: {
        "title": "511 Network Authentication Required",
        "description": "The client needs to authenticate to gain network access."
    }
}