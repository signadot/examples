const program = require('commander');
const runFrontend = require('./src/apps/frontend');

// setup OTEL auto-Instrumentation
require('./src/modules/otel/instrument.js');

program
    .option('-f, --frontend', 'run Frontend app')
    .option('-p, --producer', 'run Producer app')
    .option('-c, --consumer', 'run Consumer app')
    .parse(process.argv);

const options = program.opts();

if (options.frontend) {
    runFrontend();
} else if (options.producer) {
    // TODO
} else if (options.consumer) {
    // TODO
} else {
    console.error('Please specify a valid sub-application to run.');
    program.help();
}