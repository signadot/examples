# OpenTelemetry with Java and Spring Boot

This is a minimal example of adding OpenTelemetry auto-instrumentation to a Spring Boot app.
In contrast to the examples in the official [OpenTelemetry docs](https://opentelemetry.io/docs/instrumentation/java/examples/),
we skip over all the distributed tracing aspects since the only thing that matters
for Signadot Sandboxes is context propagation.

The directories `apiserver` and `backend` contain simple Hello World style servers.

The API server represents the point at which external requests enter the system.
The API server then makes an HTTP request to the backend server, which represents
an internal, service-to-service call.

## Without Auto-Instrumentation

You can run the two servers in separate terminal windows:

```console
$ cd apiserver
apiserver$ ./mvnw spring-boot:run
[...]
Tomcat started on port(s): 8081 (http) with context path ''
Started DemoApplication in 1.056 seconds (JVM running for 1.285)
```

```console
$ cd backend
backend$ ./mvnw spring-boot:run
[...]
Tomcat started on port(s): 8082 (http) with context path ''
Started DemoApplication in 0.909 seconds (JVM running for 1.158)
```

Then send a request to the API server that includes a `baggage` header, which is
the standard OpenTelemetry header for arbitrary context propagation:

```console
$ curl localhost:8081 -H 'baggage: sd-routing-key=abcdef'
Baggage header seen by API server: sd-routing-key=abcdef
Baggage header seen by backend server: null
```

Notice that the API server sees the `baggage` header that the client sent to it
directly, but the backend server does not. That's because there's nothing in the
API server's code to ensure that context from the incoming request is propagated
to the outgoing request to the backend.

## With Auto-Instrumentation

Terminate the two servers with Ctrl-C and then run them again, this time with
a `spring-boot.run.agents` flag that tells them to load the [OpenTelemetry Agent](https://opentelemetry.io/docs/instrumentation/java/automatic/).
We also set the `OTEL_TRACES_EXPORTER` environment variable to `none` since we
don't actually need distributed tracing in order to achieve context propagation.

```console
apiserver$ OTEL_TRACES_EXPORTER=none ./mvnw spring-boot:run -Dspring-boot.run.agents=../../opentelemetry-javaagent.jar
[...]
[INFO] Attaching agents: [.../opentelemetry-javaagent.jar]
[otel.javaagent ...] [main] INFO io.opentelemetry.javaagent.tooling.VersionLogger - opentelemetry-javaagent - version: 1.10.1
[...]
Tomcat started on port(s): 8081 (http) with context path ''
Started DemoApplication in 1.557 seconds (JVM running for 2.834)
```

```console
backend$ ./mvnw spring-boot:run -Dspring-boot.run.agents=../../opentelemetry-javaagent.jar
[...]
[INFO] Attaching agents: [.../opentelemetry-javaagent.jar]
[otel.javaagent ...] [main] INFO io.opentelemetry.javaagent.tooling.VersionLogger - opentelemetry-javaagent - version: 1.10.1
[...]
Tomcat started on port(s): 8082 (http) with context path ''
Started DemoApplication in 1.553 seconds (JVM running for 2.8)
```

Now send the request to the API server again:

```console
$ curl localhost:8081 -H 'baggage: sd-routing-key=abcdef'
Baggage header seen by API server: sd-routing-key=abcdef
Baggage header seen by backend server: sd-routing-key=abcdef
```

Notice that the `baggage` header has now been propagated all the way to the
backend server. Thanks to auto-instrumentation, no code changes were needed in
the API server to make this happen.
