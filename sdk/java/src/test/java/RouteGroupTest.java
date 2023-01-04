import com.signadot.ApiClient;
import com.signadot.ApiException;
import com.signadot.api.RouteGroupsApi;
import com.signadot.api.SandboxesApi;
import com.signadot.model.*;
import io.restassured.RestAssured;
import io.restassured.builder.RequestSpecBuilder;
import io.restassured.specification.RequestSpecification;
import org.apache.commons.lang3.RandomStringUtils;
import org.testng.annotations.AfterSuite;
import org.testng.annotations.BeforeSuite;
import org.testng.annotations.Test;

import java.util.*;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * This test creates a sandbox, and a routegroup matching the sandbox by labels, and verifies that the routegroup
 * endpoint reflects the changes introduced by the sandbox.
 *
 * Sandbox:
 * The sandbox spec contains the below customization:
 * - forks the frontend service, applying the image - `signadot/hotrod-e2e:latest`. This includes the frontend service
 *    change to return the text 'Hot R.O.D. (e2e-test)'.
 * - Applies the label: `feature: <random value>`
 *
 * Routegroup:
 * The routegroup spec contains the below customization:
 * - rule to match by label: `feature: <random value from the sandbox spec above>`
 * - endpoint to frontend service (target: http://frontend.hotrod.svc:8080)
 *
 * Test:
 * We consume the routegroup endpoint (to the frontend service), and verify that the response (HTML) contains the
 * text 'Hot R.O.D. (e2e-test)'.
 */
public class RouteGroupTest {

  private static final int TIMEOUT = 120000;
  public static final String HOTROD = "hotrod";
  public static final String ORG_NAME = System.getenv("SIGNADOT_ORG");
  public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
  public static final String CLUSTER_NAME = System.getenv("SIGNADOT_CLUSTER_NAME");

  RequestSpecification requestSpec;
  SandboxesApi sandboxesApi;
  RouteGroupsApi routeGroupsApi;
  Sandbox sb;
  RouteGroup rg;

  @BeforeSuite(timeOut = TIMEOUT)
  public void setup() throws InterruptedException, ApiException {
    ApiClient apiClient = new ApiClient();
    apiClient.setApiKey(SIGNADOT_API_KEY);
    sandboxesApi = new SandboxesApi(apiClient);
    routeGroupsApi = new RouteGroupsApi(apiClient);

    String labelKey = "feature";
    String lavelValue = RandomStringUtils.randomNumeric(5);

    sb = createSandbox(labelKey, lavelValue);
    rg = createRouteGroup(labelKey, lavelValue);

    List<RouteGroupEndpoint> endpoints = rg.getEndpoints();
    if (endpoints.size() == 0) {
      throw new RuntimeException("routegroup endpoints expected but not found");
    }

    RouteGroupEndpoint endpoint = null;
    for (RouteGroupEndpoint ep : endpoints) {
      if ("frontend-ep".equals(ep.getName())) {
        endpoint = ep;
        break;
      }
    }
    if (endpoint == null) {
      throw new RuntimeException("No routegroup endpoint found for the frontend service");
    }

    // set the base URL for tests
    RestAssured.baseURI = endpoint.getUrl();

    RequestSpecBuilder builder = new RequestSpecBuilder();
    builder.setBaseUri(RestAssured.baseURI);
    builder.addHeader("signadot-api-key", SIGNADOT_API_KEY);

    requestSpec = builder.build();
  }

  public Sandbox createSandbox(final String labelKey, final String labelValue) {
    try {
      String sandboxName = String.format("test-ws-%s", RandomStringUtils.randomNumeric(5));

      SandboxFork frontendFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("frontend"))
        .customizations(new SandboxCustomizations()
          .addImagesItem(new SandboxImage().image("signadot/hotrod-e2e:latest")));

      Map<String, String> labels = new HashMap<>();
      labels.put(labelKey, labelValue);

      Sandbox request = new Sandbox()
        .spec(new SandboxSpec()
          .labels(labels)
          .cluster(CLUSTER_NAME)
          .ttl(new SandboxTTL().duration("10m"))
          .description("Java SDK: sandbox for routegroup test")
          .addForksItem(frontendFork));

      Sandbox sandbox = sandboxesApi.applySandbox(ORG_NAME, sandboxName, request);

      // Check for sandbox readiness
      while (!sandbox.getStatus().isReady()) {
        Thread.sleep(5000);
        sandbox = sandboxesApi.getSandbox(ORG_NAME, sandboxName);
      }
      return sandbox;
    } catch (ApiException e) {
      System.out.println(e.getResponseBody());
      e.printStackTrace();
    } catch (InterruptedException e) {
      e.printStackTrace();
    }
    return null;
  }

  public RouteGroup createRouteGroup(final String labelKey, final String labelValue) throws ApiException, InterruptedException {
    try {
      String name = String.format("test-rg-%s", RandomStringUtils.randomNumeric(5));

      RouteGroup request = new RouteGroup()
        .name("java-sdk-test-rg")
        .spec(
          new RouteGroupSpec()
            .cluster(CLUSTER_NAME)
            .match(new RouteGroupMatch().label(new RouteGroupMatchLabel().key(labelKey).value(labelValue)))
            .addEndpointsItem(new RouteGroupSpecEndpoint().name("frontend-ep").target("http://frontend.hotrod.svc:8080")));

      RouteGroup routegroup = routeGroupsApi.applyRoutegroup(ORG_NAME, name, request);

      // Check for routegroup readiness
      while (!routegroup.getStatus().isReady()) {
        Thread.sleep(5000);
        routegroup = routeGroupsApi.getRoutegroup(ORG_NAME, name);
      }

      return routegroup;
    } catch (ApiException e) {
      System.out.println(e.getResponseBody());
      e.printStackTrace();
      throw e;
    } catch (InterruptedException e) {
      e.printStackTrace();
      throw e;
    }
  }

  @Test
  public void testFrontendChange() {
    given().
      spec(requestSpec).
      when().
      get("/").
      then().
      statusCode(200).
      assertThat().body(containsString("Hot R.O.D. (e2e-test)"));
  }

  @AfterSuite
  public void deleteSandbox() throws ApiException {
    sandboxesApi.deleteSandbox(ORG_NAME, sb.getName());
    routeGroupsApi.deleteRoutegroup(ORG_NAME, rg.getName());
  }
}
