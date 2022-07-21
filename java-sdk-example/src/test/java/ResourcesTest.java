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

import java.util.Arrays;
import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;

/**
 * This test creates a Sandbox with below specification:
 * - Fork HotROD Customer service
 * - Custom image of HotROD with the Customer Service code updated to include a new customer with:
 * ID=999, Name="Resources Test" and Location="123,456".
 * - Create resource using the plugin "hotrod-mariadb"
 * xref: https://github.com/signadot/hotrod/tree/main/resource-plugins/mariadb
 * This spins up an ephemeral MariaDB resource that is then used by Customer service to populate customer date.
 * The request defines the resource and env vars that are populated off of the resource.
 * <p>
 * Pre-requisites:
 * - hotrod must be installed
 * - resource plugin (hotrod-mariadb) must be installed
 * <p>
 * Once the sandbox is created with the resource, we are testing the customer service endpoint to ensure that the
 * new customer (ID=999) is obtained as expected.
 */
public class ResourcesTest {

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
  public void createSandboxWithResource() {
    apiClient = new ApiClient();
    apiClient.setApiKey(SIGNADOT_API_KEY);
    sandboxesApi = new SandboxesApi(apiClient);

    try {
      sandboxName = String.format("db-resource-test-%s", RandomStringUtils.randomAlphanumeric(5));

      SandboxFork customerServiceFork = new SandboxFork()
        .forkOf(new SandboxForkOf().kind("Deployment").namespace(HOTROD).name("customer"))
        .customizations(new SandboxCustomizations()
          .env(Arrays.asList(
              new SandboxEnvVar().name("MYSQL_HOST").valueFrom(new SandboxEnvValueFrom().resource(
                new SandboxEnvValueFromResource().name("customerdb").outputKey("host")
              )),
              new SandboxEnvVar().name("MYSQL_PORT").valueFrom(new SandboxEnvValueFrom().resource(
                new SandboxEnvValueFromResource().name("customerdb").outputKey("port")
              )),
              new SandboxEnvVar().name("MYSQL_ROOT_PASSWORD").valueFrom(new SandboxEnvValueFrom().resource(
                new SandboxEnvValueFromResource().name("customerdb").outputKey("root_password")
              ))
            )
          )
          .addImagesItem(new SandboxImage().image("signadot/hotrod:cace2c797082481ac0238cc1310b7816980e3244")))
        .addEndpointsItem(new SandboxForkEndpoint().name("customer-svc-endpoint").port(8081).protocol("http"));

      SandboxResource customerDBResource = new SandboxResource()
        .name("customerdb")
        .plugin("hotrod-mariadb")
        .putParamsItem("dbname", "customer");

      Sandbox request = new Sandbox()
        .spec(new SandboxSpec()
          .cluster(CLUSTER_NAME)
          .description("Java SDK: Create sandbox with ephemeral db resource spun up using hotrod-mariadb plugin")
          .addForksItem(customerServiceFork)
          .addResourcesItem(customerDBResource));

      sandbox = sandboxesApi.applySandbox(ORG_NAME, sandboxName, request);

      List<SandboxEndpoint> endpoints = sandbox.getEndpoints();
      if (endpoints.size() == 0) {
        throw new RuntimeException("endpoints not available in API response");
      }

      SandboxEndpoint endpoint = null;
      for (SandboxEndpoint ep : endpoints) {
        if ("customer-svc-endpoint".equals(ep.getName())) {
          endpoint = ep;
          break;
        }
      }
      if (endpoint == null) {
        throw new RuntimeException("No endpoint found for customer service");
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
  public void deleteSandbox() throws ApiException {
    sandboxesApi.deleteSandbox(ORG_NAME, sandboxName);
  }
}
