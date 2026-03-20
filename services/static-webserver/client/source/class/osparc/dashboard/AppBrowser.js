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

qx.Class.define("osparc.dashboard.AppBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "service";
    this.base(arguments);

    this.__sortBy = osparc.service.SortServicesButtons.DefaultSorting;
  },

  members: {
    __sortBy: null,
    __serviceSubmissionHelper: null,

    // overridden
    initResources: function() {
      if (this._resourcesInitialized) {
        return;
      }
      this._resourcesInitialized = true;

      this._showLoadingPage(this.tr("Loading Apps..."));
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
            const supportEmail = osparc.store.VendorInfo.getSupportEmail();
            msg += supportEmail;
            osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
          }

          this.getChildControl("resources-layout");
          this.reloadResources();
        });
    },

    reloadResources: function(useCache = true) {
      Promise.all([
        this.__loadServices(),
        this.__loadHypertools(useCache),
      ])
        .finally(() => this._hideLoadingPage());
    },

    __loadServices: function() {
      const excludeFrontend = true;
      const excludeDeprecated = true
      return osparc.store.Services.getServicesLatestList(excludeFrontend, excludeDeprecated)
        .then(servicesList => {
          servicesList.forEach(service => service["resourceType"] = "service");
          this._resourcesList.push(...servicesList.filter(service => service !== null));
          this.__sortAndReload();
        });
    },

    __loadHypertools: function(useCache = true) {
      return osparc.store.Templates.getHypertools(useCache)
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

      this.__serviceSubmissionHelper = new osparc.dashboard.ServiceSubmissionDeprecated(this._toolbar);
      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__addSortingButtons();
      this._addGroupByButton();
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
  }
});
