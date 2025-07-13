import logging
import logging.config

logger = logging.getLogger(__name__)



config: logging.config.dictConfigClass = {
    'version': 1,
    'formatters': {
        'console_formatter': {
            '()': '',
            'format': '%(name)s %(level)s %(message)s'
        },
        'file_formatter': {
            '()': '',
            'format': '%(asctime)s %(name)s %(level)s %(message)s'
        }

    },

    'filters': {},
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console_formatter',
            'level': 'INFO'
        },
        'file_handler': {
            'class': 'logging.FileHandler',
            'formatter': 'file_formatter',
            'level': 'DEBUG'
        }
    },
    'loggers': {
        'snappy_step': {
            'handlers': ['console_handler', 'file_handler'],
            'level': 'DEBUG',
            'propagate': 'False'
        }
        
    },
    'root': {
        'handlers' : ['console_handler', 'file_handler'],
        'level': 'INFO'
    }
}
