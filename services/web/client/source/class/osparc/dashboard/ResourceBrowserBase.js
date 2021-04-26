/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget (base class) that shows some resources in the Dashboard.
 *
 * It used by the three tabbed elements in the main view:
 * - Study Browser
 * - Explore Browser
 * - Data Browser
 */

qx.Class.define("osparc.dashboard.ResourceBrowserBase", {
  type: "abstract",
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._initResources();

    this.addListener("appear", () => {
      this._moreStudiesRequired();
    });
  },

  events: {
    "startStudy": "qx.event.type.Data"
  },

  statics: {
    sortStudyList: function(studyList) {
      const sortByProperty = function(prop) {
        return function(a, b) {
          if (prop === "lastChangeDate") {
            return new Date(b[prop]) - new Date(a[prop]);
          }
          if (typeof a[prop] == "number") {
            return a[prop] - b[prop];
          }
          if (a[prop] < b[prop]) {
            return -1;
          } else if (a[prop] > b[prop]) {
            return 1;
          }
          return 0;
        };
      };
      studyList.sort(sortByProperty("lastChangeDate"));
    },

    PAGINATED_STUDIES: 10,
    MIN_FILTERED_STUDIES: 15
  },

  members: {
    _studiesContainer: null,
    _loadingStudiesBtn: null,

    _initResources: function() {
      throw new Error("Abstract method called!");
    },

    _requestStudies: function(templates = false) {
      if (this._loadingStudiesBtn.isFetching()) {
        return;
      }
      this._loadingStudiesBtn.setFetching(true);
      const request = this.__getNextRequest(templates);
      request
        .then(resp => {
          const studies = resp["data"];
          this._studiesContainer.nextRequest = resp["_links"]["next"];
          this._addStudiesToList(studies);
        })
        .catch(err => {
          console.error(err);
        })
        .finally(() => {
          this._loadingStudiesBtn.setFetching(false);
          this._loadingStudiesBtn.setVisibility(this._studiesContainer.nextRequest === null ? "excluded" : "visible");
          this._moreStudiesRequired();
        });
    },

    __getNextRequest: function(templates) {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES
        }
      };
      if ("nextRequest" in this._studiesContainer &&
        this._studiesContainer.nextRequest !== null &&
        osparc.utils.Utils.hasParamFromURL(this._studiesContainer.nextRequest, "offset") &&
        osparc.utils.Utils.hasParamFromURL(this._studiesContainer.nextRequest, "limit")) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this._studiesContainer.nextRequest, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this._studiesContainer.nextRequest, "limit");
      }
      const resolveWResponse = true;
      return osparc.data.Resources.fetch(templates ? "templates" : "studies", "getPage", params, undefined, resolveWResponse);
    },

    _addStudiesToList: function() {
      throw new Error("Abstract method called!");
    },

    _moreStudiesRequired: function() {
      if (this._studiesContainer &&
        this._studiesContainer.nextRequest !== null &&
        (this._studiesContainer.getVisibles().length < osparc.dashboard.ResourceBrowserBase.MIN_FILTERED_STUDIES ||
        this._loadingStudiesBtn.checkIsOnScreen())
      ) {
        this.reloadStudies();
      }
    },

    reloadStudies: function() {
      throw new Error("Abstract method called!");
    },

    _getMoreInfoMenuButton: function(resourceData) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      osparc.utils.Utils.setIdToWidget(moreInfoButton, "moreInfoBtn");
      moreInfoButton.addListener("execute", () => {
        if (osparc.utils.Resources.isService(resourceData)) {
          this._openServiceDetails(resourceData);
        } else {
          this.__openStudyDetails(resourceData);
        }
      }, this);
      return moreInfoButton;
    },

    _getQualityMenuButton: function(resourceData) {
      const studyQualityButton = new qx.ui.menu.Button(this.tr("Quality"));
      studyQualityButton.addListener("execute", () => {
        this.__openQualityEditor(resourceData);
      }, this);
      return studyQualityButton;
    },

    __openStudyDetails: function(resourceData) {
      const studyDetails = new osparc.studycard.Large(resourceData);
      const title = this.tr("Study Details");
      const width = 500;
      const height = 500;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height);
      studyDetails.addListener("updateStudy", e => {
        if (osparc.utils.Resources.isTemplate(resourceData)) {
          const updatedTemplateData = e.getData();
          this._resetTemplateItem(updatedTemplateData);
        } else {
          const updatedStudyData = e.getData();
          this._resetStudyItem(updatedStudyData);
        }
      });
      studyDetails.addListener("updateTags", () => {
        if (osparc.utils.Resources.isTemplate(resourceData)) {
          this._resetTemplatesList(osparc.store.Store.getInstance().getTemplates());
        } else {
          this._resetStudiesList(osparc.store.Store.getInstance().getStudies());
        }
      });
    },

    _openServiceDetails: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    __openQualityEditor: function(resourceData) {
      const qualityEditor = osparc.studycard.Utils.openQuality(resourceData);
      qualityEditor.addListener("updateQuality", e => {
        const updatedResourceData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this._resetStudyItem(updatedResourceData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this._resetTemplateItem(updatedResourceData);
        } else if (osparc.utils.Resources.isService(resourceData)) {
          this._resetServiceItem(updatedResourceData);
        }
      });
    },

    _startStudy: function(studyId) {
      throw new Error("Abstract method called!");
    },

    _createStudyFromTemplate: function(templateData) {
      throw new Error("Abstract method called!");
    },

    _reloadTemplate: function(templateId) {
      throw new Error("Abstract method called!");
    },

    _resetStudyItem: function(studyData) {
      throw new Error("Abstract method called!");
    },

    _resetTemplateItem: function(templateData) {
      throw new Error("Abstract method called!");
    },

    _resetServiceItem: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    _resetStudiesList: function() {
      throw new Error("Abstract method called!");
    },

    _resetTemplatesList: function() {
      throw new Error("Abstract method called!");
    }
  }
});
