import { test, expect } from "@playwright/test";

test.describe("Ride banner", () => {
	test("shows the driver's ID", async ({ page }) => {
		await page.goto("/");
		await page.waitForLoadState();

		await page.getByRole("combobox").first().selectOption({ label: "My Home" });
		await page.getByRole("combobox").nth(1).selectOption({ label: "Rachel's Floral Designs" });
		await page.getByRole("button", { name: "Request Ride" }).click();

		await expect(
			page.getByText(/The driver .+ \(T7\d{5}C\) will arrive in \d{2}:\d{2}/),
		).toBeVisible();
	});
});
