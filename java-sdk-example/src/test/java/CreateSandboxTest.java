import com.signadot.ApiClient;
import com.signadot.ApiException;
import com.signadot.api.SandboxesApi;
import com.signadot.model.*;
import io.restassured.RestAssured;
import io.restassured.builder.RequestSpecBuilder;
import io.restassured.http.ContentType;
import io.restassured.specification.RequestSpecification;
import org.apache.commons.lang3.RandomStringUtils;
import org.testng.annotations.AfterSuite;
import org.testng.annotations.BeforeSuite;
import org.testng.annotations.Test;

import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

public class CreateSandboxTest {

    public static final String HOTROD = "hotrod";
    public static final String ORG_NAME = System.getenv("SIGNADOT_ORG");
    public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
    public static final String CLUSTER_NAME = System.getenv("SIGNADOT_CLUSTER_NAME");
    private static RequestSpecification requestSpec;

    ApiClient apiClient;
    SandboxesApi sandboxesApi;
    CreateSandboxResponse response;
    String sandboxID;

    @BeforeSuite
    public void createSandbox() throws ApiException, InterruptedException {
        apiClient = new ApiClient();
        apiClient.setApiKey(SIGNADOT_API_KEY);
        sandboxesApi = new SandboxesApi(apiClient);

        String sandboxName = String.format("test-ws-%s", RandomStringUtils.randomAlphanumeric(5));

        SandboxFork routeFork = new SandboxFork()
                .forkOf(new ForkOf().kind("Deployment").namespace(HOTROD).name("route"))
                .customizations(new SandboxCustomizations()
                        .addEnvItem(new EnvOp().name("abc").value("def").operation("upsert"))
                        .addImagesItem(new Image().image("signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd")))
                .addEndpointsItem(new ForkEndpoint().name("hotrod-route").port(8083).protocol("http"));

        CreateSandboxRequest request = new CreateSandboxRequest()
                .cluster(CLUSTER_NAME)
                .name(sandboxName)
                .description("Java SDK: sandbox creation example")
                .addForksItem(routeFork);

        response = sandboxesApi.createNewSandbox(ORG_NAME, request);

        sandboxID = response.getSandboxID();
        if (sandboxID == null || sandboxID == "") {
            throw new RuntimeException("Sandbox ID not set in API response");
        }

        List<PreviewEndpoint> endpoints = response.getPreviewEndpoints();
        if (endpoints.size() == 0) {
            throw new RuntimeException("preview endpoints not available in API response");
        }

        PreviewEndpoint endpoint = null;
        for (PreviewEndpoint ep: endpoints) {
            if ("hotrod-route".equals(ep.getName())) {
                endpoint = ep;
                break;
            }
        }
        if (endpoint == null) {
            throw new RuntimeException("No endpoint found for route service");
        }

        // set the base URL for tests
        RestAssured.baseURI = endpoint.getPreviewURL();

        RequestSpecBuilder builder = new RequestSpecBuilder();
        builder.setBaseUri(endpoint.getPreviewURL());
        builder.addHeader("signadot-api-key", SIGNADOT_API_KEY);

        requestSpec = builder.build();

        // Check for sandbox readiness
        while (!sandboxesApi.getSandboxReady(ORG_NAME, sandboxID).isReady()) {
            Thread.sleep(5000);
        };
    }

    @Test
    public void testETANotNegative() {
        given().
                spec(requestSpec).
                when().
                get("/route?pickup=123&dropoff=456").
                then().
                statusCode(200).
                assertThat().body("ETA", greaterThan(Long.valueOf(-1)));
    }

    @Test
    public void testPickupDropOffHasValue() {
        given().
                spec(requestSpec).
                when().
                get("/route?pickup=123&dropoff=456").
                then().
                statusCode(200).
                assertThat().
                body("Pickup", not(emptyOrNullString())).
                body("Dropoff", not(emptyOrNullString()));
    }

    @Test
    public void testStatusCode200() {
        given().
                spec(requestSpec).
                when().
                get("/route?pickup=123&dropoff=456").
                then().
                statusCode(200);
    }

    @Test
    public void testNoQueryParams() {
        given().
                spec(requestSpec).
                when().
                get("/route").
                then().
                statusCode(400).
                contentType(ContentType.TEXT).
                body(containsString("Missing required 'pickup' parameter"));
    }

    @Test
    public void testRequirePickupQueryParam() {
        given().
                spec(requestSpec).
                when().
                get("/route?dropoff=456").
                then().
                statusCode(400).
                contentType(ContentType.TEXT).
                body(containsString("Missing required 'pickup' parameter"));
    }

    @Test
    public void testRequireDropoffQueryParam() {
        given().
                spec(requestSpec).
                when().
                get("/route?pickup=577,322").
                then().
                statusCode(400).
                contentType(ContentType.TEXT).
                body(containsString("Missing required 'dropoff' parameter"));
    }

    @AfterSuite
    public void deleteSandbox() throws ApiException {
        sandboxesApi.deleteSandboxById(ORG_NAME, sandboxID);
    }
}
