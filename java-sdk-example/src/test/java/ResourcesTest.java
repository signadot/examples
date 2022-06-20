import com.signadot.ApiClient;
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

import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * This test creates a Sandbox with below specification:
 *   - Fork HotROD Customer service
 *   - Custom image of HotROD with the Customer Service code updated to include a new customer with:
 *       ID=999, Name="Resources Test" and Location="123,456".
 *   - Create resource using the plugin "hotrod-mariadb"
 *       xref: https://github.com/signadot/hotrod/tree/main/resource-plugins/mariadb
 *       This spins up an ephemeral MariaDB resource that is then used by Customer service to populate customer date.
 *       The request defines the resource and env vars that are populated off of the resource.
 * 
 * Pre-requisites:
 * - hotrod must be installed
 * - resource plugin (hotrod-mariadb) must be installed
 *
 * Once the sandbox is created with the resource, we are testing the customer service endpoint to ensure that the
 * new customer (ID=999) is obtained as expected.
 */
public class ResourcesTest {

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
  public void createSandboxWithResource() {
    apiClient = new ApiClient("ApiKeyAuth", SIGNADOT_API_KEY);
    sandboxesApi = apiClient.buildClient(SandboxesApi.class);

    try {
      String sandboxName = String.format("db-resource-test-%s", RandomStringUtils.randomAlphanumeric(5));
      SandboxFork customerServiceFork = new SandboxFork()
        .forkOf(new ForkOf().kind("Deployment").namespace(HOTROD).name("customer"))
        .customizations(new SandboxCustomizations()
          .env(Arrays.asList(
              new EnvOp().name("MYSQL_HOST").valueFrom(new EnvValueFrom().resource(
                new EnvValueFromResource().name("customerdb").outputKey("host")
              )),
              new EnvOp().name("MYSQL_PORT").valueFrom(new EnvValueFrom().resource(
                new EnvValueFromResource().name("customerdb").outputKey("port")
              )),
              new EnvOp().name("MYSQL_ROOT_PASSWORD").valueFrom(new EnvValueFrom().resource(
                new EnvValueFromResource().name("customerdb").outputKey("root_password")
              ))
            )
          )
          .addImagesItem(new Image().image("signadot/hotrod:cace2c797082481ac0238cc1310b7816980e3244")))
        .addEndpointsItem(new ForkEndpoint().name("customer-svc-endpoint").port(8081).protocol("http"));

      CreateSandboxRequest request = new CreateSandboxRequest()
        .cluster(CLUSTER_NAME)
        .name(sandboxName)
        .description("Java SDK: Create sandbox with ephemeral db resource spun up using hotrod-mariadb plugin")
        .addResourcesItem(
          new SandboxResource()
            .name("customerdb")
            .plugin("hotrod-mariadb")
            .putParamsItem("dbname", "customer")
        )
        .addForksItem(customerServiceFork);

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
      for (PreviewEndpoint ep : endpoints) {
        if ("customer-svc-endpoint".equals(ep.getName())) {
          endpoint = ep;
          break;
        }
      }
      if (endpoint == null) {
        throw new RuntimeException("No endpoint found for customer service");
      }

      // set the base URL for tests
      RestAssured.baseURI = endpoint.getPreviewURL();

      RequestSpecBuilder builder = new RequestSpecBuilder();
      builder.setBaseUri(endpoint.getPreviewURL());
      builder.addHeader("signadot-api-key", SIGNADOT_API_KEY);

      requestSpec = builder.build();

      // Check for sandbox readiness
      while (!sandboxesApi.getSandboxReady(ORG_NAME, sandboxID).getReady()) {
        Thread.sleep(5000);
      }
    } catch (InterruptedException e) {
      System.out.println(e.getMessage());
    }
  }

  @Test
  public void testCustomerService() {
    given().
      spec(requestSpec).
      when().
      get("/customer?customer=999").
      then().
      statusCode(200).
      assertThat().
      body("ID", equalTo(999)).
      body("Name", equalTo("Resources Test")).
      body("Location", equalTo("123,456"));
  }

  @AfterSuite
  public void deleteSandbox() {
    sandboxesApi.deleteSandboxById(ORG_NAME, sandboxID, Map.of());
  }
}
