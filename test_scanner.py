from skills.app_scanner import scan_apps, save_apps


print("Scanning apps...")

apps = scan_apps()

print("Total apps found:", len(apps))


save_apps(apps)

print("Apps saved successfully!")