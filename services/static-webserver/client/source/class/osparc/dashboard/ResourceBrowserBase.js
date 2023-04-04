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

    PAGINATED_STUDIES: 10
  },

  members: {
    _resourceType: null,
    _resourcesList: null,
    _topBar: null,
    _secondaryBar: null,
    _searchBarFilter: null,
    __viewModeLayout: null,
    _resourcesContainer: null,
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

    _createResourcesLayout: function() {
      const topBar = this.__createTopBar();
      this._add(topBar);

      const secondaryBar = this._secondaryBar = new qx.ui.toolbar.ToolBar().set({
        backgroundColor: "transparent",
        spacing: 10,
        maxHeight: 25,
        paddingRight: 8,
        alignY: "middle"
      });
      this._add(secondaryBar);

      this.__viewModeLayout = new qx.ui.toolbar.Part();

      const resourcesContainer = this._resourcesContainer = new osparc.dashboard.ResourceContainerManager();
      resourcesContainer.addListener("updateStudy", e => this._updateStudyData(e.getData()));
      resourcesContainer.addListener("updateTemplate", e => this._updateTemplateData(e.getData()));
      resourcesContainer.addListener("updateService", e => this._updateServiceData(e.getData()));
      resourcesContainer.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
      resourcesContainer.addListener("tagClicked", e => this._searchBarFilter.addTagActiveFilter(e.getData()));
      resourcesContainer.addListener("emptyStudyClicked", e => this._deleteResourceRequested(e.getData()));
      this._add(resourcesContainer);
    },

    __createTopBar: function() {
      const topBar = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        paddingRight: 8,
        alignY: "middle"
      });

      const searchBarFilter = this._searchBarFilter = new osparc.dashboard.SearchBarFilter(this._resourceType);
      const textField = searchBarFilter.getChildControl("text-field");
      osparc.utils.Utils.setIdToWidget(textField, "searchBarFilter-textField-"+this._resourceType);
      topBar.add(searchBarFilter, {
        flex: 1
      });

      return topBar;
    },

    _groupByChanged: function(groupBy) {
      // if cards are grouped they need to be in grid mode
      this._resourcesContainer.setMode("grid");
      this.__viewModeLayout.setVisibility(groupBy ? "excluded" : "visible");
      this._resourcesContainer.setGroupBy(groupBy);
      this._reloadCards();
    },

    _viewByChanged: function(viewMode) {
      this._resourcesContainer.setMode(viewMode);
      this._reloadCards();
    },

    _addGroupByButton: function() {
      const groupByMenu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const groupByButton = new qx.ui.form.MenuButton(this.tr("Group"), "@FontAwesome5Solid/chevron-down/10", groupByMenu);
      osparc.utils.Utils.setIdToWidget(groupByButton, "groupByButton");

      const groupOptions = new qx.ui.form.RadioGroup();

      const dontGroup = new qx.ui.menu.RadioButton(this.tr("None"));
      osparc.utils.Utils.setIdToWidget(dontGroup, "groupByNone");
      dontGroup.addListener("execute", () => this._groupByChanged(null));

      groupByMenu.add(dontGroup);
      groupOptions.add(dontGroup);

      if (this._resourceType === "template") {
        const tagByGroup = new qx.ui.menu.RadioButton(this.tr("Tags"));
        tagByGroup.addListener("execute", () => this._groupByChanged("tags"));
        groupByMenu.add(tagByGroup);
        groupOptions.add(tagByGroup);
        if (osparc.product.Utils.isProduct("s4llite")) {
          tagByGroup.execute();
        }
      }

      const groupByShared = new qx.ui.menu.RadioButton(this.tr("Shared with"));
      groupByShared.addListener("execute", () => this._groupByChanged("shared"));
      groupByMenu.add(groupByShared);
      groupOptions.add(groupByShared);

      this._secondaryBar.add(groupByButton);
    },

    _getToolbarButton: function(label, icon, toolTipText) {
      return new qx.ui.toolbar.Button().set({
        margin: 0,
        label,
        icon,
        toolTipText
      });
    },

    _addViewModeButton: function() {
      const gridBtn = this._getToolbarButton(null, "@FontAwesome5Solid/th/14", this.tr("Grid view"));
      gridBtn.addListener("execute", () => this._viewByChanged("grid"));

      const listBtn = this._getToolbarButton(null, "@FontAwesome5Solid/bars/14", this.tr("List view"));
      listBtn.addListener("execute", () => this._viewByChanged("list"));

      const viewModeLayout = this.__viewModeLayout;
      [
        gridBtn,
        listBtn
      ].forEach(btn => {
        viewModeLayout.add(btn);
      });

      this._secondaryBar.add(viewModeLayout);
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

    _removeResourceCards: function() {
      const cards = this._resourcesContainer.getCards();
      for (let i=cards.length-1; i>=0; i--) {
        const card = cards[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
          this._resourcesContainer.removeNonResourceCard(card);
        }
      }
    },

    _moreResourcesRequired: function() {
      if (this._resourcesContainer && this._resourcesContainer.areMoreResourcesRequired(this._loadingResourcesBtn)) {
        this.reloadResources();
      }
    },

    _taskDataReceived: function(taskData) {
      throw new Error("Abstract method called!");
    },

    _populateCardMenu: function(card) {
      throw new Error("Abstract method called!");
    },

    _updateStudyData: function(studyData) {
      throw new Error("Abstract method called!");
    },

    _updateTemplateData: function(templateData) {
      throw new Error("Abstract method called!");
    },

    _updateServiceData: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    _createStudyFromService: function() {
      throw new Error("Abstract method called!");
    },

    _deleteResourceRequested: function(resourceId) {
      throw new Error("Abstract method called!");
    },

    _getMoreOptionsMenuButton: function(resourceData) {
      const moreOptsButton = new qx.ui.menu.Button(this.tr("More options..."));
      osparc.utils.Utils.setIdToWidget(moreOptsButton, "moreInfoBtn");
      moreOptsButton.addListener("execute", () => {
        const moreOpts = new osparc.dashboard.ResourceMoreOptions(resourceData);
        const title = this.tr("Options");
        const win = osparc.ui.window.Window.popUpInWindow(
          moreOpts,
          title,
          osparc.dashboard.ResourceMoreOptions.WIDTH,
          osparc.dashboard.ResourceMoreOptions.HEIGHT
        );
        moreOpts.addListener("updateStudy", e => this._updateStudyData(e.getData()));
        moreOpts.addListener("updateTemplate", e => this._updateTemplateData(e.getData()));
        moreOpts.addListener("updateService", e => this._updateServiceData(e.getData()));
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
    },

    _getShareMenuButton: function(card) {
      const resourceData = card.getResourceData();
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(resourceData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const shareButton = new qx.ui.menu.Button(this.tr("Share..."));
      shareButton.addListener("tap", () => card.openAccessRights(), this);
      return shareButton;
    }
  }
});
