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
    "publishTemplate": "qx.event.type.Data"
  },

  statics: {
    PAGINATED_STUDIES: 10,

    checkLoggedIn: function() {
      const isLogged = osparc.auth.Manager.getInstance().isLoggedIn();
      if (!isLogged) {
        const msg = qx.locale.Manager.tr("You need to be logged in to create a study");
        osparc.FlashMessenger.getInstance().logAs(msg);
      }
      return isLogged;
    },

    startStudyById: function(studyId, openCB, cancelCB, isStudyCreation = false) {
      if (!osparc.dashboard.ResourceBrowserBase.checkLoggedIn()) {
        return;
      }

      const openStudy = () => {
        if (openCB) {
          openCB();
        }
        osparc.desktop.MainPageHandler.getInstance().startStudy(studyId);
      };

      const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
      if (walletsEnabled) {
        const params = {
          url: {
            studyId
          }
        };
        osparc.data.Resources.fetch("studies", "getWallet", params)
          .then(wallet => {
            if (isStudyCreation || wallet === null || osparc.desktop.credits.Utils.getWallet(wallet["walletId"]) === null) {
              // pop up study options if the study was just created or if it has no wallet assigned or user has no access to it
              const resourceSelector = new osparc.study.StudyOptions(studyId);
              const win = osparc.study.StudyOptions.popUpInWindow(resourceSelector);
              win.moveItUp();
              resourceSelector.addListener("startStudy", () => {
                win.close();
                openStudy();
              });
              win.addListener("cancel", () => {
                if (cancelCB) {
                  cancelCB();
                }
              });
              resourceSelector.addListener("cancel", () => {
                win.close();
                if (cancelCB) {
                  cancelCB();
                }
              });
              // listen to "tap" instead of "execute": the "execute" is not propagated
              win.getChildControl("close-button").addListener("tap", () => {
                if (cancelCB) {
                  cancelCB();
                }
              });
            } else {
              openStudy();
            }
          })
          .catch(err => {
            console.error(err);
            osparc.FlashMessenger.logAs(err.message, "ERROR");
          });
      } else {
        openStudy();
      }
    },

    sortStudyList: function(studyList, sortValue) {
      const sortByProperty = function(prop) {
        return function(a, b) {
          const x = a.toString().toLowerCase();
          const y = b.toString().toLowerCase();
          if (prop === "lastChangeDate") {
            return new Date(y[prop]) - new Date(x[prop]);
          }
          if (typeof x[prop] == "number") {
            return x[prop] - y[prop];
          }
          if (x[prop] < y[prop]) {
            return -1;
          } else if (x[prop] > y[prop]) {
            return 1;
          }
          return 0;
        };
      };
      studyList.sort(sortByProperty(sortValue || "name"));
    },

    isCardNewItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonNew || card instanceof osparc.dashboard.ListButtonNew);
    },

    isCardButtonItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonItem || card instanceof osparc.dashboard.ListButtonItem);
    },

    createToolbarRadioButton: function(label, icon, toolTipText, pos) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        icon,
        toolTipText,
        padding: 5,
        paddingLeft: 8,
        paddingRight: 8,
        margin: 0
      });
      rButton.getContentElement().setStyles({
        "border-radius": "0px"
      });
      if (pos === "left") {
        osparc.utils.Utils.addBorderLeftRadius(rButton);
      } else if (pos === "right") {
        osparc.utils.Utils.addBorderRightRadius(rButton);
      }
      return rButton;
    }
  },

  members: {
    _resourceType: null,
    _resourcesList: null,
    _topBar: null,
    _toolbar: null,
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

      const toolbar = this._toolbar = new qx.ui.toolbar.ToolBar().set({
        backgroundColor: "transparent",
        spacing: 10,
        paddingRight: 8,
        alignY: "middle"
      });
      this._add(toolbar);

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
        paddingRight: 22,
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
      groupByButton.set({
        appearance: "form-button-outlined",
        marginRight: 14
      });
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
        if (
          osparc.product.Utils.isProduct("s4l") ||
          osparc.product.Utils.isProduct("s4lacad") ||
          osparc.product.Utils.isProduct("s4llite")
        ) {
          tagByGroup.execute();
        }
      }

      const groupByShared = new qx.ui.menu.RadioButton(this.tr("Shared with"));
      groupByShared.addListener("execute", () => this._groupByChanged("shared"));
      groupByMenu.add(groupByShared);
      groupOptions.add(groupByShared);

      this._toolbar.add(groupByButton);
    },

    _addViewModeButton: function() {
      const gridBtn = this.self().createToolbarRadioButton(null, "@FontAwesome5Solid/th/14", this.tr("Grid view"), "left");
      gridBtn.addListener("execute", () => this._viewByChanged("grid"));

      const listBtn = this.self().createToolbarRadioButton(null, "@FontAwesome5Solid/bars/14", this.tr("List view"), "right");
      listBtn.addListener("execute", () => this._viewByChanged("list"));

      const viewModeLayout = this.__viewModeLayout;
      const radioGroup = new qx.ui.form.RadioGroup();
      [
        gridBtn,
        listBtn
      ].forEach(btn => {
        viewModeLayout.add(btn);
        radioGroup.add(btn);
      });

      this._toolbar.add(viewModeLayout);
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
        osparc.FlashMessenger.getInstance().logAs(msg);
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

    _startStudyById: function(studyId, openCB, cancelCB, isStudyCreation = false) {
      this.self().startStudyById(studyId, openCB, cancelCB, isStudyCreation);
    },

    _createStudyFromTemplate: function() {
      throw new Error("Abstract method called!");
    },

    _createStudyFromService: async function() {
      throw new Error("Abstract method called!");
    },

    _deleteResourceRequested: function(resourceId) {
      throw new Error("Abstract method called!");
    },

    _getOpenMenuButton: function(resourceData) {
      const openButton = new qx.ui.menu.Button(this.tr("Open"));
      openButton.openResource = true;
      openButton.addListener("execute", () => {
        switch (resourceData["resourceType"]) {
          case "study": {
            const isStudyCreation = false;
            this._startStudyById(resourceData["uuid"], null, null, isStudyCreation);
            break;
          }
          case "template":
            this._createStudyFromTemplate(resourceData);
            break;
          case "service":
            this._createStudyFromService(resourceData["key"], resourceData["version"]);
            break;
        }
      }, this);
      return openButton;
    },

    _openDetailsView: function(resourceData) {
      const resourceDetails = new osparc.dashboard.ResourceDetails(resourceData);
      const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
      resourceDetails.addListener("updateStudy", e => this._updateStudyData(e.getData()));
      resourceDetails.addListener("updateTemplate", e => this._updateTemplateData(e.getData()));
      resourceDetails.addListener("updateService", e => this._updateServiceData(e.getData()));
      resourceDetails.addListener("publishTemplate", e => {
        win.close();
        this.fireDataEvent("publishTemplate", e.getData());
      });
      resourceDetails.addListener("openStudy", e => {
        const openCB = () => win.close();
        const studyId = e.getData()["uuid"];
        const isStudyCreation = false;
        this._startStudyById(studyId, openCB, null, isStudyCreation);
      });
      resourceDetails.addListener("openTemplate", e => {
        win.close();
        const templateData = e.getData();
        this._createStudyFromTemplate(templateData);
      });
      resourceDetails.addListener("openService", e => {
        win.close();
        const openServiceData = e.getData();
        this._createStudyFromService(openServiceData["key"], openServiceData["version"]);
      });
      return resourceDetails;
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
    },

    _getTagsMenuButton: function(card) {
      const resourceData = card.getResourceData();
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(resourceData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const tagsButton = new qx.ui.menu.Button(this.tr("Tags..."));
      tagsButton.addListener("tap", () => card.openTags(), this);
      return tagsButton;
    }
  }
});
