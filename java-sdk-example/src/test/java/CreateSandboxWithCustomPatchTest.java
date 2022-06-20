import com.signadot.ApiClient;
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
import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

public class CreateSandboxWithCustomPatchTest {

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
  CreateSandboxResponse response;
  String envVarValue;
  String sandboxID;

  /**
   * Forks the hotrod customer container. The customer container is customized with a custom patch
   * that sets the PATCH_TEST_VAR environment variable to a random string. The image used for the customer
   * container has been customized so that the custom environment variable is returned from the customer
   * endpoint, so we can validate that it has the expected value.
   */
  @BeforeSuite
  public void createSandboxWithCustomPatch() throws InterruptedException {
    apiClient = new ApiClient("ApiKeyAuth", SIGNADOT_API_KEY);
    sandboxesApi = apiClient.buildClient(SandboxesApi.class);

    envVarValue = RandomStringUtils.randomAlphanumeric(5);
    final String customPatch = String.format(CUSTOM_PATCH, envVarValue);
    String sandboxName = String.format("custom-patch-test-%s", RandomStringUtils.randomAlphanumeric(5));

    SandboxFork customerFork = new SandboxFork()
      .forkOf(new ForkOf().kind("Deployment").namespace(HOTROD).name("customer"))
      .customizations(new SandboxCustomizations()
        .addImagesItem(new Image().image(HOTROD_TEST_IMAGE))
        .patch(new CustomPatch().type("strategic").value(customPatch)))
      .addEndpointsItem(new ForkEndpoint().name("hotrod-customer").port(8081).protocol("http"));

    CreateSandboxRequest request = new CreateSandboxRequest()
      .cluster(CLUSTER_NAME)
      .name(sandboxName)
      .description("Java SDK: sandbox creation with custom patch example")
      .addForksItem(customerFork);

    response = sandboxesApi.createNewSandbox(ORG_NAME, request);

    sandboxID = response.getSandboxID();
    if (sandboxID == null || sandboxID.isBlank()) {
      throw new RuntimeException("Sandbox ID not set in API response");
    }

    List<PreviewEndpoint> endpoints = response.getPreviewEndpoints();
    if (endpoints.size() == 0) {
      throw new RuntimeException("preview endpoints not available in API response");
    }

    PreviewEndpoint endpoint = null;
    for (PreviewEndpoint ep : endpoints) {
      if ("hotrod-customer".equals(ep.getName())) {
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
    while (Boolean.FALSE.equals(sandboxesApi.getSandboxReady(ORG_NAME, sandboxID).getReady())) {
      Thread.sleep(5000);
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
  public void deleteSandbox() {
    sandboxesApi.deleteSandboxById(ORG_NAME, sandboxID, Map.of());
  }
}
