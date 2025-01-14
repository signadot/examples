const program = require('commander');

// setup OTEL auto-Instrumentation
require('./src/modules/otel/instrument.js');

const runFrontend = require('./src/apps/frontend/app.js');
const runPublisher = require('./src/apps/publisher/app.js');
const runSubscriber = require('./src/apps/subscriber/app.js');

program
    .option('-f, --frontend', 'run Frontend app')
    .option('-p, --publisher', 'run Publisher app')
    .option('-s, --subscriber', 'run Subscriber app')
    .parse(process.argv);

const options = program.opts();

if (options.frontend) {
    runFrontend();
} else if (options.publisher) {
    runPublisher();
} else if (options.subscriber) {
    runSubscriber();
} else {
    console.error('Please specify a valid sub-application to run.');
    program.help();
}