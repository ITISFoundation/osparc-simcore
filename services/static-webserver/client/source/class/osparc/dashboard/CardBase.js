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

qx.Class.define("osparc.dashboard.CardBase", {
  extend: qx.ui.form.ToggleButton,
  implement: [qx.ui.form.IModel, osparc.component.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.component.filter.MFilterable],
  type: "abstract",

  construct: function() {
    this.base(arguments);

    [
      "pointerover",
      "focus"
    ].forEach(e => this.addListener(e, this._onPointerOver, this));

    [
      "pointerout",
      "focusout"
    ].forEach(e => this.addListener(e, this._onPointerOut, this));
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data"
  },

  statics: {
    SHARED_USER: "@FontAwesome5Solid/user/14",
    SHARED_ORGS: "@FontAwesome5Solid/users/14",
    SHARED_ALL: "@FontAwesome5Solid/globe/14",
    NEW_ICON: "@FontAwesome5Solid/plus/",
    LOADING_ICON: "@FontAwesome5Solid/circle-notch/",
    STUDY_ICON: "@FontAwesome5Solid/file-alt/",
    TEMPLATE_ICON: "@FontAwesome5Solid/copy/",
    SERVICE_ICON: "@FontAwesome5Solid/paw/",
    COMP_SERVICE_ICON: "@FontAwesome5Solid/cogs/",
    DYNAMIC_SERVICE_ICON: "@FontAwesome5Solid/mouse-pointer/",
    PERM_READ: "@FontAwesome5Solid/eye/14",
    MODE_WORKBENCH: "@FontAwesome5Solid/cubes/14",
    MODE_GUIDED: "@FontAwesome5Solid/play/14",
    MODE_APP: "@FontAwesome5Solid/desktop/14",

    CARD_PRIORITY: {
      NEW: 0,
      PLACEHOLDER: 1,
      ITEM: 2,
      LOADER: 3
    },

    filterText: function(checks, text) {
      if (text) {
        const includesSome = checks.some(check => check.toLowerCase().trim().includes(text.toLowerCase()));
        return !includesSome;
      }
      return false;
    },

    filterTags: function(checks, tags) {
      if (tags && tags.length) {
        const includesAll = tags.every(tag => checks.includes(tag));
        return !includesAll;
      }
      return false;
    },

    filterClassifiers: function(checks, classifiers) {
      if (classifiers && classifiers.length) {
        const includesAll = classifiers.every(classifier => checks.includes(classifier));
        return !includesAll;
      }
      return false;
    }
  },

  properties: {
    appearance: {
      refine : true,
      init : "pb-listitem"
    },

    cardKey: {
      check: "String",
      nullable: true,
      init: null
    },

    resourceData: {
      check: "Object",
      nullable: false,
      init: null,
      apply: "__applyResourceData"
    },

    resourceType: {
      check: ["study", "template", "service"],
      nullable: false,
      event: "changeResourceType"
    },

    uuid: {
      check: "String",
      apply: "__applyUuid"
    },

    title: {
      check: "String",
      apply: "_applyTitle",
      nullable: true
    },

    description: {
      check: "String",
      apply: "_applyDescription",
      nullable: true
    },

    owner: {
      check: "String",
      apply: "_applyOwner",
      nullable: true
    },

    accessRights: {
      check: "Object",
      apply: "_applyAccessRights",
      nullable: true
    },

    lastChangeDate: {
      check: "Date",
      apply: "_applyLastChangeDate",
      nullable: true
    },

    classifiers: {
      check: "Array"
    },

    tags: {
      check: "Array",
      apply: "_applyTags"
    },

    quality: {
      check: "Object",
      nullable: true,
      apply: "__applyQuality"
    },

    workbench: {
      check: "Object",
      nullable: true,
      apply: "__applyWorkbench"
    },

    uiMode: {
      check: ["workbench", "guided", "app"],
      nullable: true,
      apply: "__applyUiMode"
    },

    hits: {
      check: "Number",
      nullable: true,
      apply: "__applyHits"
    },

    state: {
      check: "Object",
      nullable: false,
      apply: "_applyState"
    },

    locked: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyLocked"
    },

    menu: {
      check: "qx.ui.menu.Menu",
      nullable: true,
      apply: "_applyMenu",
      event: "changeMenu"
    },

    multiSelectionMode: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyMultiSelectionMode"
    },

    fetching: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyFetching"
    },

    priority: {
      check: "Number",
      init: null,
      nullable: false
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    // overridden
    _forwardStates: {
      focused : true,
      hovered : true,
      selected : true,
      dragover : true
    },

    isResourceType: function(resourceType) {
      return this.getResourceType() === resourceType;
    },

    __applyResourceData: function(studyData) {
      let defaultThumbnail = "";
      let uuid = null;
      let owner = "";
      let accessRights = {};
      let defaultHits = null;
      let workbench = null;
      switch (studyData["resourceType"]) {
        case "study":
          uuid = studyData.uuid ? studyData.uuid : uuid;
          owner = studyData.prjOwner ? studyData.prjOwner : owner;
          accessRights = studyData.accessRights ? studyData.accessRights : accessRights;
          defaultThumbnail = this.self().STUDY_ICON;
          workbench = studyData.workbench ? studyData.workbench : workbench;
          break;
        case "template":
          uuid = studyData.uuid ? studyData.uuid : uuid;
          owner = studyData.prjOwner ? studyData.prjOwner : owner;
          accessRights = studyData.accessRights ? studyData.accessRights : accessRights;
          defaultThumbnail = this.self().TEMPLATE_ICON;
          workbench = studyData.workbench ? studyData.workbench : workbench;
          break;
        case "service":
          uuid = studyData.key ? studyData.key : uuid;
          owner = studyData.owner ? studyData.owner : owner;
          accessRights = studyData.access_rights ? studyData.access_rights : accessRights;
          defaultThumbnail = this.self().SERVICE_ICON;
          if (osparc.data.model.Node.isComputational(studyData)) {
            defaultThumbnail = this.self().COMP_SERVICE_ICON;
          }
          if (osparc.data.model.Node.isDynamic(studyData)) {
            defaultThumbnail = this.self().DYNAMIC_SERVICE_ICON;
          }
          defaultHits = 0;
          break;
      }

      this.set({
        resourceType: studyData.resourceType,
        uuid,
        title: studyData.name,
        description: studyData.description,
        owner,
        accessRights,
        lastChangeDate: studyData.lastChangeDate ? new Date(studyData.lastChangeDate) : null,
        icon: studyData.thumbnail || defaultThumbnail,
        state: studyData.state ? studyData.state : {},
        classifiers: studyData.classifiers && studyData.classifiers ? studyData.classifiers : [],
        quality: studyData.quality ? studyData.quality : null,
        uiMode: studyData.ui && studyData.ui.mode ? studyData.ui.mode : null,
        hits: studyData.hits ? studyData.hits : defaultHits,
        workbench
      });
    },

    __applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);

      this.setCardKey(value);
    },

    _applyIcon: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyTitle: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyDescription: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyOwner: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyLastChangeDate: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyAccessRights: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyTags: function(tags) {
      throw new Error("Abstract method called!");
    },

    __applyQuality: function(quality) {
      if (osparc.component.metadata.Quality.isEnabled(quality)) {
        const tsrRating = this.getChildControl("tsr-rating");
        tsrRating.set({
          nStars: 4,
          showScore: true
        });
        osparc.ui.basic.StarsRating.scoreToStarsRating(quality["tsr_current"], quality["tsr_target"], tsrRating);
        // Stop propagation of the pointer event in case the tag is inside a button that we don't want to trigger
        tsrRating.addListener("tap", e => {
          e.stopPropagation();
          this.__openQualityEditor();
        }, this);
        tsrRating.addListener("pointerdown", e => e.stopPropagation());
      }
    },

    __applyUiMode: function(uiMode) {
      let source = null;
      let toolTipText = null;
      switch (uiMode) {
        case "guided":
        case "app":
          source = osparc.dashboard.CardBase.MODE_APP;
          toolTipText = this.tr("App mode");
          break;
      }
      if (source) {
        const uiModeIcon = this.getChildControl("ui-mode");
        uiModeIcon.set({
          source,
          toolTipText
        });
      }
    },

    __applyHits: function(hits) {
      if (hits !== null) {
        const hitsLabel = this.getChildControl("hits-service");
        hitsLabel.setValue(this.tr("Hits: ") + String(hits));
      }
    },

    __applyWorkbench: function(workbench) {
      if (workbench === null) {
        return;
      }

      const updateStudy = this.getChildControl("update-study");
      updateStudy.addListener("pointerdown", e => e.stopPropagation());
      updateStudy.addListener("tap", e => {
        e.stopPropagation();
        this.__openUpdateServices();
      }, this);
      if (osparc.utils.Study.isWorkbenchRetired(workbench)) {
        updateStudy.show();
        updateStudy.set({
          toolTipText: this.tr("Service(s) retired, please update"),
          textColor: osparc.utils.StatusUI.getColor("retired")
        });
      } else if (osparc.utils.Study.isWorkbenchDeprecated(workbench)) {
        updateStudy.show();
        updateStudy.set({
          toolTipText: this.tr("Service(s) deprecated, please update"),
          textColor: osparc.utils.StatusUI.getColor("deprecated")
        });
      } else {
        osparc.utils.Study.isWorkbenchUpdatable(workbench)
          .then(updatable => {
            if (updatable) {
              updateStudy.show();
              updateStudy.set({
                toolTipText: this.tr("Update available"),
                textColor: "text"
              });
            }
          });
      }

      osparc.utils.Study.getUnaccessibleServices(workbench)
        .then(unaccessibleServices => {
          if (unaccessibleServices.length) {
            this.setLocked(true);
            const image = "@FontAwesome5Solid/ban/";
            let toolTipText = this.tr("Service info missing");
            unaccessibleServices.forEach(unSrv => {
              toolTipText += "<br>" + unSrv.key + ":" + unSrv.version;
            });
            this.__blockCard(image, toolTipText);
          }
        });
    },

    _applyState: function(state) {
      const locked = ("locked" in state) ? state["locked"]["value"] : false;
      this.setLocked(locked);
      if (locked) {
        this.__setLockedStatus(state["locked"]);
      }
    },

    __setLockedStatus: function(lockedStatus) {
      const status = lockedStatus["status"];
      const owner = lockedStatus["owner"];
      let toolTip = osparc.utils.Utils.firstsUp(owner["first_name"], owner["last_name"]);
      let image = null;
      switch (status) {
        case "CLOSING":
          image = "@FontAwesome5Solid/key/";
          toolTip += this.tr(" is closing it...");
          break;
        case "CLONING":
          image = "@FontAwesome5Solid/clone/";
          toolTip += this.tr(" is cloning it...");
          break;
        case "EXPORTING":
          image = osparc.component.task.Export.ICON+"/";
          toolTip += this.tr(" is exporting it...");
          break;
        case "OPENING":
          image = "@FontAwesome5Solid/key/";
          toolTip += this.tr(" is opening it...");
          break;
        case "OPENED":
          image = "@FontAwesome5Solid/lock/";
          toolTip += this.tr(" is using it.");
          break;
        default:
          image = "@FontAwesome5Solid/lock/";
          break;
      }
      this.__blockCard(image, toolTip);
    },

    __blockCard: function(lockImageSrc, toolTipText) {
      const lockImage = this.getChildControl("lock-status").getChildControl("image");
      lockImageSrc += this.classname.includes("Grid") ? "70" : "22";
      lockImage.setSource(lockImageSrc);
      if (toolTipText) {
        this.set({
          toolTipText
        });
      }
    },

    _applyLocked: function(locked) {
      this.__enableCard(!locked);
      this.getChildControl("lock-status").set({
        opacity: 1.0,
        visibility: locked ? "visible" : "excluded"
      });
    },

    __enableCard: function(enabled) {
      this.set({
        cursor: enabled ? "pointer" : "not-allowed"
      });
      if (enabled) {
        this.resetToolTipText();
      }

      this._getChildren().forEach(item => {
        item.setOpacity(enabled ? 1.0 : 0.4);
      });

      [
        "tick-selected",
        "tick-unselected",
        "menu-button"
      ].forEach(childName => {
        const child = this.getChildControl(childName);
        child.set({
          enabled
        });
      });
    },

    _applyFetching: function(value) {
      throw new Error("Abstract method called!");
    },

    _applyMenu: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _setStudyPermissions: function(accessRights) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
      orgIDs.push(myGroupId);

      const permissionIcon = this.getChildControl("permission-icon");
      if (osparc.component.permissions.Study.canGroupsWrite(accessRights, orgIDs)) {
        permissionIcon.exclude();
      } else {
        permissionIcon.setSource(osparc.dashboard.CardBase.PERM_READ);
        this.addListener("mouseover", () => permissionIcon.show(), this);
        this.addListener("mouseout", () => permissionIcon.exclude(), this);
      }
    },

    __openMoreOptions: function() {
      const resourceData = this.getResourceData();
      const moreOpts = new osparc.dashboard.ResourceMoreOptions(resourceData);
      const title = this.tr("More options");
      const win = osparc.ui.window.Window.popUpInWindow(moreOpts, title, 750, 725);
      [
        "updateStudy",
        "updateTemplate",
        "updateService"
      ].forEach(ev => {
        moreOpts.addListener(ev, e => this.fireDataEvent(ev, e.getData()));
      });
      moreOpts.addListener("publishTemplate", e => {
        win.close();
        this.fireDataEvent("publishTemplate", e.getData());
      });
      return moreOpts;
    },

    _openAccessRights: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openAccessRights();
    },

    __openQualityEditor: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openQuality();
    },

    __openUpdateServices: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openUpdateServices();
    },

    /**
     * Event handler for the pointer over event.
     */
    _onPointerOver: function() {
      this.addState("hovered");
    },

    /**
     * Event handler for the pointer out event.
     */
    _onPointerOut : function() {
      this.removeState("hovered");
    },

    /**
     * Event handler for filtering events.
     */
    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _filterText: function(text) {
      const checks = [
        this.getTitle(),
        this.getDescription(),
        this.getOwner()
      ];
      return this.self().filterText(checks, text);
    },

    _filterTags: function(tags) {
      const checks = this.getTags().map(tag => tag.name);
      return this.self().filterTags(checks, tags);
    },

    _filterClassifiers: function(classifiers) {
      const checks = this.getClassifiers();
      return this.self().filterClassifiers(checks, classifiers);
    },

    _shouldApplyFilter: function(data) {
      let filterId = "searchBarFilter";
      if (this.isPropertyInitialized("resourceType")) {
        filterId += "-" + this.getResourceType();
      }
      data = filterId in data ? data[filterId] : data;
      if (this._filterText(data.text)) {
        return true;
      }
      if (this._filterTags(data.tags)) {
        return true;
      }
      if (this._filterClassifiers(data.classifiers)) {
        return true;
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      let filterId = "searchBarFilter";
      if (this.isPropertyInitialized("resourceType")) {
        filterId += "-" + this.getResourceType();
      }
      data = filterId in data ? data[filterId] : data;
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      if (data.classifiers && data.classifiers.length) {
        return true;
      }
      return false;
    }
  },

  destruct: function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
