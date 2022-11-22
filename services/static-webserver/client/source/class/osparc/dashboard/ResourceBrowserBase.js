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
 * It used by the following tabbed elements in the main view:
 * - Study Browser
 * - Template Browser
 * - Service Browser
 */

qx.Class.define("osparc.dashboard.ResourceBrowserBase", {
  type: "abstract",
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._showLoadingPage(this.tr("Starting..."));

    this.addListener("appear", () => this._moreResourcesRequired());
  },

  events: {
    "startStudy": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data"
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

    isCardNewItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonNew || card instanceof osparc.dashboard.ListButtonNew);
    },

    isCardButtonItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonItem || card instanceof osparc.dashboard.ListButtonItem);
    },

    PAGINATED_STUDIES: 10,
    MIN_FILTERED_STUDIES: 15
  },

  members: {
    _topBar: null,
    _secondaryBar: null,
    _resourcesContainer: null,
    _viewGridBtn: null,
    _viewListBtn: null,
    _loadingResourcesBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "resources-layout": {
          const scroll = new qx.ui.container.Scroll();
          scroll.getChildControl("pane").addListener("scrollY", () => this._moreResourcesRequired(), this);
          control = this._createLayout();
          scroll.add(control);
          this._add(scroll, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    initResources: function() {
      throw new Error("Abstract method called!");
    },

    reloadResources: function() {
      throw new Error("Abstract method called!");
    },

    _createLayout: function() {
      throw new Error("Abstract method called!");
    },

    _createResourcesLayout: function(resourceType) {
      const topBar = this.__createTopBar(resourceType);
      this._add(topBar);

      const secondaryBar = this._secondaryBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      this._add(secondaryBar);

      const spacing = osparc.dashboard.GridButtonBase.SPACING;
      const resourcesContainer = this._resourcesContainer = new osparc.dashboard.ToggleButtonContainer(new qx.ui.layout.Flow(spacing, spacing));
      this._add(resourcesContainer);
    },

    __createTopBar: function(resourceType) {
      const topBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(12)).set({
        paddingRight: 8,
        alignY: "middle"
      });

      const searchBarFilter = new osparc.dashboard.SearchBarFilter(resourceType);
      const textField = searchBarFilter.getChildControl("text-field");
      osparc.utils.Utils.setIdToWidget(textField, resourceType ? "searchBarFilter-textField-"+resourceType : "searchBarFilter-textField");
      topBar.add(searchBarFilter, {
        flex: 1
      });

      const containterModeBtns = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
      const viewGridBtn = this._viewGridBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/apps/18");
      const viewListBtn = this._viewListBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/reorder/18");
      const group = new qx.ui.form.RadioGroup();
      [
        viewGridBtn,
        viewListBtn
      ].forEach(btn => {
        containterModeBtns.add(btn);
        group.add(btn);
        btn.getContentElement().setStyles({
          "border-radius": "8px"
        });
      });
      topBar.add(containterModeBtns);

      viewGridBtn.addListener("execute", () => this._resourcesContainer.setMode("grid"));
      viewListBtn.addListener("execute", () => this._resourcesContainer.setMode("list"));

      return topBar;
    },

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this._resourcesContainer) {
        this._resourcesContainer.resetSelection();
      }
    },

    _showMainLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    _checkLoggedIn: function() {
      let isLogged = osparc.auth.Manager.getInstance().isLoggedIn();
      if (!isLogged) {
        const msg = this.tr("You need to be logged in to create a study");
        osparc.component.message.FlashMessenger.getInstance().logAs(msg);
      }
      return isLogged;
    },

    _addResourcesToList: function() {
      throw new Error("Abstract method called!");
    },

    _removeResourceCards: function() {
      const cards = this._resourcesContainer.getChildren();
      for (let i=cards.length-1; i>=0; i--) {
        const card = cards[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
          this._resourcesContainer.remove(card);
        }
      }
    },

    _moreResourcesRequired: function() {
      if (this._resourcesContainer && this._resourcesContainer.areMoreResourcesRequired(this._loadingResourcesBtn)) {
        this.reloadResources();
      }
    },

    _createResourceItem: function(resourceData) {
      const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];

      const item = this._resourcesContainer.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      item.set({
        resourceData,
        tags
      });

      const menu = this._getResourceItemMenu(resourceData, item);
      item.setMenu(menu);
      item.subscribeToFilterGroup("searchBarFilter");

      return item;
    },

    _taskDataReceived: function(taskData) {
      throw new Error("Abstract method called!");
    },

    _getResourceItemMenu: function(resourceData, item) {
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

    _resetResourcesList: function(resourcesList) {
      throw new Error("Abstract method called!");
    },

    _createStudyFromService: function() {
      throw new Error("Abstract method called!");
    },

    _getMoreOptionsMenuButton: function(resourceData) {
      const moreOptsButton = new qx.ui.menu.Button(this.tr("More options..."));
      osparc.utils.Utils.setIdToWidget(moreOptsButton, "moreInfoBtn");
      moreOptsButton.addListener("execute", () => {
        const moreOpts = new osparc.dashboard.ResourceMoreOptions(resourceData);
        const title = this.tr("More options");
        const win = osparc.ui.window.Window.popUpInWindow(moreOpts, title, 750, 725);
        moreOpts.addListener("updateStudy", e => {
          const updatedStudyData = e.getData();
          this._resetStudyItem(updatedStudyData);
        });
        moreOpts.addListener("updateTemplate", e => {
          const updatedTemplateData = e.getData();
          this._resetTemplateItem(updatedTemplateData);
        });
        moreOpts.addListener("updateService", e => {
          const updatedServiceData = e.getData();
          this._resetServiceItem(updatedServiceData);
        });
        moreOpts.addListener("publishTemplate", e => {
          win.close();
          this.fireDataEvent("publishTemplate", e.getData());
        });
        moreOpts.addListener("openService", e => {
          win.close();
          const openServiceData = e.getData();
          this._createStudyFromService(openServiceData["key"], openServiceData["version"]);
        });
      }, this);
      return moreOptsButton;
    }
  }
});
