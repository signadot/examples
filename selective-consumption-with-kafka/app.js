const program = require('commander');

// setup OTEL auto-Instrumentation
require('./src/modules/otel/instrument.js');

const runFrontend = require('./src/apps/frontend/app.js');
const runProducer = require('./src/apps/producer/app.js');
const runConsumer = require('./src/apps/consumer/app.js');

program
    .option('-f, --frontend', 'run Frontend app')
    .option('-p, --producer', 'run Producer app')
    .option('-c, --consumer', 'run Consumer app')
    .parse(process.argv);

const options = program.opts();

if (options.frontend) {
    runFrontend();
} else if (options.producer) {
    runProducer();
} else if (options.consumer) {
    runConsumer();
} else {
    console.error('Please specify a valid sub-application to run.');
    program.help();
}