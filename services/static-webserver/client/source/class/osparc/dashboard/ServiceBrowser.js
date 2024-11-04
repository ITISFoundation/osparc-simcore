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

qx.Class.define("osparc.dashboard.ServiceBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "service";
    this.base(arguments);

    this.__sortBy = osparc.service.SortServicesButtons.DefaultSorting;
  },

  properties: {
    multiSelection: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelection",
      apply: "__applyMultiSelection"
    }
  },

  members: {
    __sortBy: null,

    // overridden
    initResources: function() {
      this._resourcesList = [];
      this.getChildControl("resources-layout");
      this.reloadResources();
      this._hideLoadingPage();
    },

    reloadResources: function() {
      this.__loadServices();
    },

    __loadServices: function() {
      const excludeFrontend = true;
      const excludeDeprecated = true
      osparc.store.Services.getServicesLatestList(excludeFrontend, excludeDeprecated)
        .then(servicesList => this.__setServicesToList(servicesList));
    },

    _updateServiceData: function(serviceData) {
      serviceData["resourceType"] = "service";
      const servicesList = this._resourcesList;
      const index = servicesList.findIndex(service => service["key"] === serviceData["key"] && service["version"] === serviceData["version"]);
      if (index !== -1) {
        servicesList[index] = serviceData;
        this._reloadCards();
      }
    },

    __setServicesToList: function(servicesList) {
      servicesList.forEach(service => service["resourceType"] = "service");
      osparc.service.Utils.sortObjectsBasedOn(servicesList, this.__sortBy);
      this._resourcesList = servicesList;
      this._reloadCards();
    },

    _reloadCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("services");
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("execute", () => this.__itemClicked(card), this);
        this._populateCardMenu(card);
      });
      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __itemClicked: function(card) {
      const serviceData = card.getResourceData();
      this._openResourceDetails(serviceData);
      this.resetSelection();
    },

    _createStudyFromService: function(key, version) {
      if (!this._checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating ") + osparc.product.Utils.getStudyAlias());
      osparc.study.Utils.createStudyFromService(key, version)
        .then(studyId => {
          const openCB = () => this._hideLoadingPage();
          const cancelCB = () => {
            this._hideLoadingPage();
            const params = {
              url: {
                studyId
              }
            };
            osparc.data.Resources.fetch("studies", "delete", params);
          };
          const isStudyCreation = true;
          this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    // LAYOUT //
    _createLayout: function() {
      this._createSearchBar();
      this._createResourcesLayout();
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "servicesList");
      }

      this.__addNewServiceButtons();
      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__addSortingButtons();
      this._addGroupByButton();
      this._addViewModeButton();

      this._addResourceFilter();

      return this._resourcesContainer;
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

      const addServiceButton = new qx.ui.form.Button(this.tr("Submit new service"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.set({
        appearance: "form-button-outlined",
        visibility: hasRights ? "visible" : "excluded"
      });
      addServiceButton.addListener("execute", () => this.__displayServiceSubmissionForm());
      this._toolbar.add(addServiceButton);
    },

    __addSortingButtons: function() {
      const containerSortButtons = new osparc.service.SortServicesButtons();
      containerSortButtons.set({
        appearance: "form-button-outlined"
      });
      containerSortButtons.addListener("sortBy", e => {
        this.__sortBy = e.getData();
        this.__setServicesToList(this._resourcesList);
      }, this);
      this._toolbar.add(containerSortButtons);
    },

    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const serviceData = card.getResourceData();

      const openButton = this._getOpenMenuButton(serviceData);
      if (openButton) {
        menu.add(openButton);
      }
    },

    __displayServiceSubmissionForm: function(formData) {
      const addServiceWindow = new osparc.ui.window.Window(this.tr("Submit a new service")).set({
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
