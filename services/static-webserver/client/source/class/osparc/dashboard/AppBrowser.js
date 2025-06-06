/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(form/service.json)
 * @asset(form/service-data.json)
 * @ignore(Headers)
 * @ignore(fetch)
 */

qx.Class.define("osparc.dashboard.AppBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "service";
    this.base(arguments);

    this.__sortBy = osparc.service.SortServicesButtons.DefaultSorting;

    const groupedServicesConfig = osparc.store.Products.getInstance().getGroupedServicesUiConfig();
    if (groupedServicesConfig) {
      console.log("groupedServices", groupedServicesConfig);
    }
  },

  members: {
    __sortBy: null,

    // overridden
    initResources: function() {
      if (this._resourcesInitialized) {
        return;
      }
      this._resourcesInitialized = true;

      this._resourcesList = [];
      Promise.all([
        osparc.store.Services.getServicesLatest(),
        osparc.store.Templates.getHypertools(),
      ])
        .then(resps => {
          const services = resps[0];
          // Show "Contact Us" message if services.length === 0
          // Most probably is a product-stranger user (it can also be that the catalog is down)
          if (Object.keys(services).length === 0) {
            let msg = this.tr("It seems you don't have access to this product.");
            msg += "</br>";
            msg += this.tr("Please contact us:");
            msg += "</br>";
            const supportEmail = osparc.store.VendorInfo.getInstance().getSupportEmail();
            msg += supportEmail;
            osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
          }

          this.getChildControl("resources-layout");
          this.reloadResources();
          this._hideLoadingPage();
        });
    },

    reloadResources: function(useCache = true) {
      this.__loadServices();
      this.__loadHypertools(useCache);
    },

    __loadServices: function() {
      const excludeFrontend = true;
      const excludeDeprecated = true
      osparc.store.Services.getServicesLatestList(excludeFrontend, excludeDeprecated)
        .then(servicesList => {
          servicesList.forEach(service => service["resourceType"] = "service");
          this._resourcesList.push(...servicesList.filter(service => service !== null));
          this.__sortAndReload();
        });
    },

    __loadHypertools: function(useCache = true) {
      osparc.store.Templates.getHypertools(useCache)
        .then(hypertoolsList => {
          hypertoolsList.forEach(hypertool => hypertool["resourceType"] = "hypertool");
          this._resourcesList.push(...hypertoolsList.filter(hypertool => hypertool !== null));
          this.__sortAndReload();
        });
    },

    __sortAndReload: function() {
      osparc.service.Utils.sortObjectsBasedOn(this._resourcesList, this.__sortBy);
      this._reloadCards();
    },

    _updateServiceData: function(serviceData) {
      serviceData["resourceType"] = "service";
      const appsList = this._resourcesList;
      const index = appsList.findIndex(service => service["key"] === serviceData["key"] && service["version"] === serviceData["version"]);
      if (index !== -1) {
        appsList[index] = serviceData;
        this._reloadCards();
      }
    },

    _updateHypertoolData: function(hypertoolData) {
      hypertoolData["resourceType"] = "hypertool";
      const appsList = this._resourcesList;
      const index = appsList.findIndex(service => service["uuid"] === hypertoolData["uuid"]);
      if (index !== -1) {
        appsList[index] = hypertoolData;
        this._reloadCards();
      }
    },

    _reloadCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("services");
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("tap", () => this.__itemClicked(card), this);
        this._populateCardMenu(card);
      });
      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __itemClicked: function(card) {
      const appData = card.getResourceData();
      this._openResourceDetails(appData);
      this.resetSelection();
    },

    // LAYOUT //
    _createLayout: function() {
      this._createSearchBar();
      this._createResourcesLayout("servicesList");

      this.__addNewServiceButtons();
      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__addSortingButtons();
      if (osparc.product.Utils.groupServices()) {
        this._resourcesContainer.setGroupBy("groupedServices");
      }
      this._addViewModeButton();

      this._addResourceFilter();

      return this._resourcesContainer;
    },

    __addSortingButtons: function() {
      const containerSortButtons = new osparc.service.SortServicesButtons();
      containerSortButtons.set({
        appearance: "form-button-outlined"
      });
      containerSortButtons.addListener("sortBy", e => {
        this.__sortBy = e.getData();
        this.__sortAndReload();
      }, this);
      this._toolbar.add(containerSortButtons);
    },

    _populateCardMenu: function(card) {
      const studyData = card.getResourceData();
      if (studyData["resourceType"] === "hypertool") {
        // The App Browser can also list templates (hypertools)
        this._populateTemplateCardMenu(card);
      } else {
        this._populateServiceCardMenu(card);
      }
    },

    _populateServiceCardMenu: function(card) {
      const menu = card.getMenu();
      const appData = card.getResourceData();

      const openButton = this._getOpenMenuButton(appData);
      if (openButton) {
        menu.add(openButton);
      }
    },

    __addNewServiceButtons: function() {
      const platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
      const hasRights = osparc.data.Permissions.getInstance().canDo("studies.template.create.productAll");
      if (platformName === "dev") {
        const testDataButton = new qx.ui.form.Button(this.tr("Test with data"), "@FontAwesome5Solid/plus-circle/14");
        testDataButton.addListener("execute", () => {
          osparc.utils.Utils.fetchJSON("/resource/form/service-data.json")
            .then(data => {
              this.__displayServiceSubmissionForm(data);
            });
        });
        this._toolbar.add(testDataButton);
      }

      const addServiceButton = new qx.ui.form.Button(this.tr("Submit new app"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.set({
        appearance: "form-button-outlined",
        visibility: hasRights ? "visible" : "excluded"
      });
      addServiceButton.addListener("execute", () => this.__displayServiceSubmissionForm());
      this._toolbar.add(addServiceButton);
    },

    __displayServiceSubmissionForm: function(formData) {
      const addServiceWindow = new osparc.ui.window.Window(this.tr("Submit a new app")).set({
        modal: true,
        autoDestroy: true,
        showMinimize: false,
        allowMinimize: false,
        centerOnAppear: true,
        layout: new qx.ui.layout.Grow(),
        width: 600,
        height: 660
      });
      const scroll = new qx.ui.container.Scroll();
      addServiceWindow.add(scroll);
      const form = new osparc.form.json.JsonSchemaForm("/resource/form/service.json", formData);
      form.addListener("ready", () => {
        addServiceWindow.open();
      });
      form.addListener("submit", e => {
        const data = e.getData();
        const headers = new Headers();
        headers.append("Accept", "application/json");
        const body = new FormData();
        body.append("metadata", new Blob([JSON.stringify(data.json)], {
          type: "application/json"
        }));
        if (data.files && data.files.length) {
          const size = data.files[0].size;
          const maxSize = 10 * 1000 * 1000; // 10 MB
          if (size > maxSize) {
            osparc.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          body.append("attachment", data.files[0], data.files[0].name);
        }
        form.setFetching(true);
        fetch("/v0/publications/service-submission", {
          method: "POST",
          headers,
          body
        })
          .then(resp => {
            if (resp.ok) {
              osparc.FlashMessenger.logAs("Your data was sent to our curation team. We will get back to you shortly.", "INFO");
              addServiceWindow.close();
            } else {
              osparc.FlashMessenger.logAs(`A problem occurred while processing your data: ${resp.statusText}`, "ERROR");
            }
          })
          .finally(() => form.setFetching(false));
      });
      scroll.add(form);
    }
  }
});
