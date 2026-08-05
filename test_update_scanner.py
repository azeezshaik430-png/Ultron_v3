from skills.app_scanner import update_apps, load_apps


print("Updating App Database...\n")


new_apps = update_apps()


print("New apps found:")

if new_apps:

    for app in new_apps:
        print("-", app)

else:

    print("No new apps")


print("\nTotal apps in database:", len(load_apps()))