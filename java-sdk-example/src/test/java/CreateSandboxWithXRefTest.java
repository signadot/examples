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
import static org.hamcrest.Matchers.*;

public class CreateSandboxWithXRefTest {

  private static final int TIMEOUT = 120000;
  public static final String HOTROD = "hotrod";
  public static final String HOTROD_TEST_IMAGE = "signadot/hotrod:49aa0813feba0fb74e4edccdde27702605de07e0";

  public static final String ORG_NAME = System.getenv("SIGNADOT_ORG");
  public static final String SIGNADOT_API_KEY = System.getenv("SIGNADOT_API_KEY");
  public static final String CLUSTER_NAME = System.getenv("SIGNADOT_CLUSTER_NAME");

  private static RequestSpecification requestSpec;

  ApiClient apiClient;
  SandboxesApi sandboxesApi;
  Sandbox sandbox;
  String sandboxName;

  /**
   * Forks the hotrod customer and frontend containers. It is customized with the
   * FROM_TEST_VAR environment variable that comes from the frontend container using a template expression.
   * The image used for the customer container has been customized so that the custom environment variable
   * is returned from the customer endpoint, so we can validate that it has the expected value. Though since
   * we can't be sure what is going to be put into FROM_TEST_VAR, we only validate that there is content for it
   * in the response.
   */
  @BeforeSuite(timeOut = TIMEOUT)
  public void createSandboxWithXRef() {
    try {
      apiClient = new ApiClient();
      apiClient.setApiKey(SIGNADOT_API_KEY);
      sandboxesApi = new SandboxesApi(apiClient);

      sandboxName = String.format("xref-test-%s", RandomStringUtils.randomAlphanumeric(5));

      SandboxFork frontendFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("frontend"))
        .customizations(new SandboxCustomizations()
          .addImagesItem(new SandboxImage().image(HOTROD_TEST_IMAGE))
        );

      SandboxFork customerFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("customer"))
        .customizations(new SandboxCustomizations()
          .addImagesItem(new SandboxImage().image(HOTROD_TEST_IMAGE))
          .addEnvItem(new SandboxEnvVar().name("FROM_TEST_VAR").valueFrom(
            new SandboxEnvValueFrom().fork(
              new SandboxEnvValueFromFork().forkOf(
                new SandboxForkOf()
                  .kind("Deployment")
                  .namespace("hotrod")
                  .name("frontend")
              ).expression("{{ .Service.Host }}:{{ .Service.Port }}")
            )
          ))
        )
        .addEndpointsItem(new SandboxForkEndpoint().name("hotrod-customer").port(8081).protocol("http"));

      Sandbox request = new Sandbox()
        .spec(new SandboxSpec()
          .cluster(CLUSTER_NAME)
          .description("Java SDK: sandbox creation with cross fork reference example")
          .addForksItem(customerFork)
          .addForksItem(frontendFork));

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
      .body("FromVar", not(is(emptyOrNullString())));
  }

  @AfterSuite
  public void deleteSandbox() throws ApiException {
    sandboxesApi.deleteSandbox(ORG_NAME, sandboxName);
  }
}
