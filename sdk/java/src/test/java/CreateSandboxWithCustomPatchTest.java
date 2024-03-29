import com.signadot.ApiClient;
import com.signadot.ApiException;
import com.signadot.api.SandboxesApi;
import com.signadot.model.*;
import io.restassured.RestAssured;
import io.restassured.builder.RequestSpecBuilder;
import io.restassured.specification.RequestSpecification;
import org.apache.commons.lang3.RandomStringUtils;
import org.testng.annotations.AfterSuite;
import org.testng.annotations.BeforeSuite;
import org.testng.annotations.Test;

import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;

public class CreateSandboxWithCustomPatchTest {

  private static final int TIMEOUT = 120000;
  public static final String HOTROD = "hotrod";
  public static final String HOTROD_TEST_IMAGE = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0";
  public static final String CUSTOM_PATCH = "spec:\n" +
    "  template:\n" +
    "    spec:\n" +
    "      containers:\n" +
    "      - name: hotrod\n" +
    "        env:\n" +
    "        - name:  PATCH_TEST_VAR\n" +
    "          value: %s\n";

  public static final String ORG_NAME = System.getenv("SIGNADOT_ORG");
  public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
  public static final String CLUSTER_NAME = System.getenv("SIGNADOT_CLUSTER_NAME");

  private static RequestSpecification requestSpec;

  ApiClient apiClient;
  SandboxesApi sandboxesApi;
  Sandbox sandbox;
  String envVarValue;
  String sandboxName;

  /**
   * Forks the hotrod customer container. The customer container is customized with a custom patch
   * that sets the PATCH_TEST_VAR environment variable to a random string. The image used for the customer
   * container has been customized so that the custom environment variable is returned from the customer
   * endpoint, so we can validate that it has the expected value.
   */
  @BeforeSuite(timeOut = TIMEOUT)
  public void createSandboxWithCustomPatch() throws InterruptedException {
    apiClient = new ApiClient();
    apiClient.setApiKey(SIGNADOT_API_KEY);
    sandboxesApi = new SandboxesApi(apiClient);

    try {
      envVarValue = RandomStringUtils.randomAlphanumeric(5);
      final String customPatch = String.format(CUSTOM_PATCH, envVarValue);
      sandboxName = String.format("custom-patch-test-%s", RandomStringUtils.randomNumeric(5));

      SandboxFork customerFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("customer"))
        .customizations(new SandboxCustomizations()
          .addImagesItem(new SandboxImage().image(HOTROD_TEST_IMAGE))
          .patch(new SandboxCustomPatch().type("strategic").value(customPatch)));

      SandboxDefaultRouteGroup drg = new SandboxDefaultRouteGroup()
        .addEndpointsItem(new RouteGroupSpecEndpoint().name("hotrod-customer").target("http://customer.hotrod.deploy:8081"));

      Sandbox request = new Sandbox()
        .spec(new SandboxSpec()
          .cluster(CLUSTER_NAME)
          .ttl(new SandboxTTL().duration("10m"))
          .description("Java SDK: sandbox creation with custom patch example")
          .addForksItem(customerFork)
          .defaultRouteGroup(drg));

      sandbox = sandboxesApi.applySandbox(ORG_NAME, sandboxName, request);

      List<SandboxEndpoint> endpoints = sandbox.getEndpoints();
      if (endpoints.size() == 0) {
        throw new RuntimeException("endpoints not available in API response");
      }

      SandboxEndpoint endpoint = null;
      for (SandboxEndpoint ep : endpoints) {
        if ("hotrod-customer".equals(ep.getName())) {
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
  public void testCustomEnvVars() {
    given()
      .spec(requestSpec)
      .when()
      .get("/customer?customer=392")
      .then()
      .statusCode(200)
      .assertThat()
      .body("PatchVar", equalTo(envVarValue));
  }

  @AfterSuite
  public void deleteSandbox() throws ApiException {
    sandboxesApi.deleteSandbox(ORG_NAME, sandboxName);
  }
}
