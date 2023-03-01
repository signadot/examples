# OpenTelemetry with Node.js and hapi

This is a minimal example of adding OpenTelemetry auto-instrumentation to a hapi app.
In contrast to the examples in the official [OpenTelemetry docs](https://opentelemetry.io/docs/instrumentation/js/getting-started/nodejs/),
we skip over all the distributed tracing aspects since the only thing that matters
for Signadot Sandboxes is context propagation.

The files `apiserver.js` and `backend.js` are simple Hello World style hapi servers.

The API server represents the point at which external requests enter the system.
The API server then makes an HTTP request to the backend server, which represents
an internal, service-to-service call.

## Without Auto-Instrumentation

You can run the two servers in separate terminal windows:

```console
$ npm install
$ node apiserver.js
API server running on http://localhost:3000
```

```console
$ node backend.js
Backend server running on http://localhost:3001
```

Then send a request to the API server that includes a `baggage` header, which is
the standard OpenTelemetry header for arbitrary context propagation:

```console
$ curl localhost:3000 -H 'baggage: sd-routing-key=abcdef'
Baggage header seen by API server: sd-routing-key=abcdef
Baggage header seen by backend server: undefined
```

Notice that the API server sees the `baggage` header that the client sent to it
directly, but the backend server does not. That's because there's nothing in the
API server's code to ensure that context from the incoming request is propagated
to the outgoing request to the backend.

## With Auto-Instrumentation

Terminate the two servers with Ctrl-C and then run them again, this time with
a `--require` flag that tells them to load the `instrument.js` file:

```console
$ node --require './instrument.js' apiserver.js
API server running on http://localhost:3000
```

```console
$ node --require './instrument.js' backend.js
Backend server running on http://localhost:3001
```

Now send the request to the API server again:

```console
$ curl localhost:3000 -H 'baggage: sd-routing-key=abcdef'
Baggage header seen by API server: sd-routing-key=abcdef
Baggage header seen by backend server: sd-routing-key=abcdef
```

Notice that the `baggage` header has now been propagated all the way to the
backend server. Thanks to auto-instrumentation, no code changes were needed in
the API server to make this happen.

See the `package.json` file for the list of dependencies that were used by the
`instrument.js` file to enable auto-instrumentation at program startup.
