import com.signadot.ApiClient;
import com.signadot.ApiException;
import com.signadot.api.WorkspacesApi;
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

// This test uses the -SNAPSHOT version of the sdk and is running against the staging environment. Update this to use
// the release version and run against prod after the release (0.1.4)
public class RouteServiceTest {

    public static final String ORG_NAME = "signadot";
    public static final String HOTROD = "hotrod";
    public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
    private static RequestSpecification requestSpec;

    ApiClient apiClient;
    WorkspacesApi workspacesApi;
    CreateWorkspaceResponse response;
    String workspaceID;

    @BeforeSuite
    public void createWorkspace() throws ApiException, InterruptedException {
        apiClient = new ApiClient();
        apiClient.setApiKey(SIGNADOT_API_KEY);
        workspacesApi = new WorkspacesApi(apiClient);

        String workspaceName = String.format("test-ws-%s", RandomStringUtils.randomAlphanumeric(5));
        WorkspaceFork routeFork = new WorkspaceFork()
                .forkOf(new ForkOf().kind("Deployment").namespace(HOTROD).name("route"))
                .customizations(new WorkspaceCustomizations()
                        .addEnvItem(new EnvOp().name("abc").value("def").operation("upsert"))
                        .addImagesItem(new Image().image("signadot/hotrod-route:540fadfd2fe619e20b794d56ce404761ce2b45a3")))
                .addEndpointsItem(new ForkEndpoint().name("hotrod-route").port(8083).protocol("http"));

        CreateWorkspaceRequest request = new CreateWorkspaceRequest()
                .cluster("demo")
                .name(workspaceName)
                .description("test workspace created using java-sdk")
                .addForksItem(routeFork);

        response = workspacesApi.createNewWorkspace(ORG_NAME, request);

        workspaceID = response.getWorkspaceID();
        if (workspaceID == null || workspaceID == "") {
            throw new RuntimeException("Workspace ID not set in API response");
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

        // Check for workspace readiness
        while (!workspacesApi.getWorkspaceReady(ORG_NAME, workspaceID).isReady()) {
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
    public void deleteWorkspace() throws ApiException {
        workspacesApi.deleteWorkspaceById(ORG_NAME, workspaceID);
    }
}
