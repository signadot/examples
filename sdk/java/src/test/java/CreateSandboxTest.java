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

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

public class CreateSandboxTest {

  private static final int TIMEOUT = 120000;
  public static final String HOTROD = "hotrod";
  public static final String ORG_NAME = System.getenv("SIGNADOT_ORG");
  public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
  public static final String CLUSTER_NAME = System.getenv("SIGNADOT_CLUSTER_NAME");
  private static RequestSpecification requestSpec;

  ApiClient apiClient;
  SandboxesApi sandboxesApi;
  Sandbox sandbox;
  String sandboxName;

  @BeforeSuite(timeOut = TIMEOUT)
  public void createSandbox() {
    try {
      apiClient = new ApiClient();
      apiClient.setApiKey(SIGNADOT_API_KEY);
      sandboxesApi = new SandboxesApi(apiClient);

      sandboxName = String.format("test-ws-%s", RandomStringUtils.randomNumeric(5));

      SandboxFork routeFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("route"))
        .customizations(new SandboxCustomizations()
          .addEnvItem(new SandboxEnvVar().name("abc").value("def"))
          .addImagesItem(new SandboxImage().image("signadot/hotrod:0ed0bdadaa3af1e4f1e6f3bb6b7d19504aa9b1bd")));

      Map<String, String> labels = new HashMap<>();
      labels.put("key1", "value1");
      labels.put("key2", "value2");

      SandboxDefaultRouteGroup drg = new SandboxDefaultRouteGroup()
        .addEndpointsItem(new RouteGroupSpecEndpoint().name("hotrod-route").target("http://route.hotrod.deploy:8083"));

      Sandbox request = new Sandbox()
        .spec(new SandboxSpec()
          .labels(labels)
          .cluster(CLUSTER_NAME)
          .ttl(new SandboxTTL().duration("10m"))
          .description("Java SDK: sandbox creation example")
          .addForksItem(routeFork)
          .defaultRouteGroup(drg));

      sandbox = sandboxesApi.applySandbox(ORG_NAME, sandboxName, request);

      List<SandboxEndpoint> endpoints = sandbox.getEndpoints();
      if (endpoints.size() == 0) {
        throw new RuntimeException("endpoints not available in API response");
      }

      SandboxEndpoint endpoint = null;
      for (SandboxEndpoint ep : endpoints) {
        if ("hotrod-route".equals(ep.getName())) {
          endpoint = ep;
          break;
        }
      }
      if (endpoint == null) {
        throw new RuntimeException("No endpoint found for route service");
      }

      // set the base URL for tests
      RestAssured.baseURI = endpoint.getUrl();

      RequestSpecBuilder builder = new RequestSpecBuilder();
      builder.setBaseUri(RestAssured.baseURI);
      builder.addHeader("signadot-api-key", SIGNADOT_API_KEY);

      requestSpec = builder.build();

      // Check for sandbox readiness
      while (!sandbox.getStatus().isReady()) {
        Thread.sleep(5000);
        sandbox = sandboxesApi.getSandbox(ORG_NAME, sandboxName);
      }
    } catch (ApiException e) {
      System.out.println(e.getResponseBody());
      e.printStackTrace();
    } catch (InterruptedException e) {
      e.printStackTrace();
    }
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
    sandboxesApi.deleteSandbox(ORG_NAME, sandboxName);
  }
}
