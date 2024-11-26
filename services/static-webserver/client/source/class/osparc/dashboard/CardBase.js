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
  implement: [qx.ui.form.IModel, osparc.filter.IFilterable],
  include: [qx.ui.form.MModelProperty, osparc.filter.MFilterable],
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
    "publishTemplate": "qx.event.type.Data",
    "tagClicked": "qx.event.type.Data",
    "emptyStudyClicked": "qx.event.type.Data"
  },

  statics: {
    SHARE_ICON: "@FontAwesome5Solid/share-alt/13",
    SHARED_USER: "@FontAwesome5Solid/user/13",
    SHARED_ORGS: "@FontAwesome5Solid/users/13",
    SHARED_ALL: "@FontAwesome5Solid/globe/13",
    PERM_READ: "@FontAwesome5Solid/eye/13",
    MODE_APP: "@FontAwesome5Solid/desktop/13",
    NEW_ICON: "@FontAwesome5Solid/plus/",
    LOADING_ICON: "@FontAwesome5Solid/circle-notch/",
    // Get the default thumbnail for each product else add the image and extension osparc.product.Utils.getProductThumbUrl(Thumbnail-01.png)
    PRODUCT_ICON: osparc.product.Utils.getProductThumbUrl(),

    CARD_PRIORITY: {
      NEW: 0,
      PLACEHOLDER: 1,
      ITEM: 2,
      LOADER: 3
    },

    createTSRLayout: function() {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2).set({
        alignY: "middle"
      })).set({
        toolTipText: qx.locale.Manager.tr("Ten Simple Rules"),
        minWidth: 85
      });
      const tsrLabel = new qx.ui.basic.Label(qx.locale.Manager.tr("TSR:")).set({
        alignY: "middle"
      });
      layout.add(tsrLabel);
      const tsrRating = new osparc.ui.basic.StarsRating().set({
        alignY: "middle"
      });
      layout.add(tsrRating);
      return layout;
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

    filterSharedWith: function(checks, sharedWith) {
      if (sharedWith && sharedWith !== "show-all") {
        const groupsStore = osparc.store.Groups.getInstance();
        const myGroupId = groupsStore.getMyGroupId();
        if (checks && myGroupId in checks) {
          const myAccessRights = checks[myGroupId];
          const totalAccess = "delete" in myAccessRights ? myAccessRights["delete"] : myAccessRights["write"];
          if (sharedWith === "my-resources") {
            return !totalAccess;
          } else if (sharedWith === "shared-with-me") {
            return totalAccess;
          } else if (sharedWith === "shared-with-everyone") {
            const everyoneGroupIds = [
              groupsStore.getEveryoneProductGroup().getGroupId(),
              groupsStore.getEveryoneGroup().getGroupId(),
            ];
            const found = Object.keys(checks).some(gId => everyoneGroupIds.includes(parseInt(gId)));
            return !found;
          }
          return false;
        }
        // if we get here, it means that it was shared-with-me via an organization
        if (sharedWith === "shared-with-me") {
          return false;
        }
        return true;
      }
      return false;
    },

    filterServiceType: function(resourceType, metadata, serviceType) {
      if (serviceType && resourceType === "service") {
        if (metadata && metadata.type) {
          const matches = metadata.type === serviceType;
          return !matches;
        }
        return false;
      }
      return false;
    },

    filterClassifiers: function(checks, classifiers) {
      if (classifiers && classifiers.length) {
        const includesAll = classifiers.every(classifier => checks.includes(classifier));
        return !includesAll;
      }
      return false;
    },

    // groups -> [orgMembs, orgs, [productEveryone], [everyone]];
    setIconAndTooltip: function(shareIcon, accessRights, groups) {
      shareIcon.setSource(osparc.dashboard.CardBase.SHARE_ICON);
      if (osparc.data.model.Study.canIWrite(accessRights)) {
        shareIcon.set({
          toolTipText: qx.locale.Manager.tr("Share")
        });
      }
      let sharedGrps = [];
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      for (let i=0; i<groups.length; i++) {
        if (groups[i].length === 0) {
          // user has no read access to the productEveryone
          continue;
        }
        const sharedGrp = [];
        const gids = Object.keys(accessRights);
        for (let j=0; j<gids.length; j++) {
          const gid = parseInt(gids[j]);
          if (gid === myGroupId) {
            continue;
          }
          const grp = groups[i].find(group => group.getGroupId() === gid);
          if (grp) {
            sharedGrp.push(grp);
          }
        }
        if (sharedGrp.length === 0) {
          continue;
        } else {
          sharedGrps = sharedGrps.concat(sharedGrp);
        }
        switch (i) {
          case 0:
            shareIcon.setSource(osparc.dashboard.CardBase.SHARED_USER);
            break;
          case 1:
            shareIcon.setSource(osparc.dashboard.CardBase.SHARED_ORGS);
            break;
          case 2:
          case 3:
            shareIcon.setSource(osparc.dashboard.CardBase.SHARED_ALL);
            break;
        }
      }

      // tooltip
      if (sharedGrps.length === 0) {
        return;
      }
      const sharedGrpLabels = [];
      const maxItems = 6;
      for (let i=0; i<sharedGrps.length; i++) {
        if (i > maxItems) {
          sharedGrpLabels.push("...");
          break;
        }
        const sharedGrpLabel = sharedGrps[i].getLabel();
        if (!sharedGrpLabels.includes(sharedGrpLabel)) {
          sharedGrpLabels.push(sharedGrpLabel);
        }
      }
      const hintText = sharedGrpLabels.join("<br>");
      const hint = new osparc.ui.hint.Hint(shareIcon, hintText);
      shareIcon.addListener("mouseover", () => hint.show(), this);
      shareIcon.addListener("mouseout", () => hint.exclude(), this);
    },

    // groups -> [orgMembs, orgs, [productEveryone], [everyone]];
    populateShareIcon: function(shareIcon, accessRights) {
      const groupsStore = osparc.store.Groups.getInstance();
      const orgMembs = Object.values(groupsStore.getReachableUsers());
      const orgs = Object.values(groupsStore.getOrganizations());
      const productEveryone = [groupsStore.getEveryoneProductGroup()];
      const everyone = [groupsStore.getEveryoneGroup()];
      const groups = [orgMembs, orgs, productEveryone, everyone];
      osparc.dashboard.CardBase.setIconAndTooltip(shareIcon, accessRights, groups);
    },
  },

  properties: {
    appearance: {
      refine : true,
      init : "pb-listitem"
    },

    cardKey: {
      check: "String",
      nullable: true
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

    emptyWorkbench: {
      check: "Boolean",
      nullable: false,
      init: null,
      event: "changeEmptyWorkbench",
      apply: "__applyEmptyWorkbench"
    },

    updatable: {
      check: [null, "retired", "deprecated", "updatable"],
      nullable: false,
      init: null,
      event: "changeUpdatable",
      apply: "__applyUpdatable"
    },

    hits: {
      check: "Number",
      nullable: true,
      apply: "__applyHits"
    },

    state: {
      check: "Object",
      nullable: false,
      apply: "__applyState"
    },

    projectState: {
      check: ["NOT_STARTED", "STARTED", "SUCCESS", "FAILED", "UNKNOWN"],
      nullable: false,
      init: "UNKNOWN",
      apply: "_applyProjectState"
    },

    blocked: {
      check: [true, "UNKNOWN_SERVICES", "IN_USE", false],
      init: false,
      nullable: false,
      apply: "__applyBlocked"
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

    isItemNotClickable: function() {
      const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
      return (
        this.getBlocked() === true || // It could be blocked by IN_USE or UNKNOWN_SERVICE
        (this.isResourceType("study") && (studyBrowserContext === "trash")) // It could a trashed study
      );
    },

    __applyResourceData: function(resourceData) {
      let uuid = null;
      let owner = null;
      let workbench = null;
      let defaultHits = null;
      switch (resourceData["resourceType"]) {
        case "study":
          uuid = resourceData.uuid ? resourceData.uuid : null;
          owner = resourceData.prjOwner ? resourceData.prjOwner : "";
          workbench = resourceData.workbench ? resourceData.workbench : {};
          break;
        case "template":
          uuid = resourceData.uuid ? resourceData.uuid : null;
          owner = resourceData.prjOwner ? resourceData.prjOwner : "";
          workbench = resourceData.workbench ? resourceData.workbench : {};
          break;
        case "service":
          uuid = resourceData.key ? resourceData.key : null;
          owner = resourceData.owner ? resourceData.owner : resourceData.contact;
          defaultHits = 0;
          break;
      }

      this.set({
        resourceType: resourceData.resourceType,
        uuid,
        title: resourceData.name,
        description: resourceData.description,
        owner,
        accessRights: resourceData.accessRights ? resourceData.accessRights : {},
        lastChangeDate: resourceData.lastChangeDate ? new Date(resourceData.lastChangeDate) : null,
        icon: resourceData.thumbnail || this.self().PRODUCT_ICON,
        state: resourceData.state ? resourceData.state : {},
        classifiers: resourceData.classifiers && resourceData.classifiers ? resourceData.classifiers : [],
        quality: resourceData.quality ? resourceData.quality : null,
        uiMode: resourceData.ui && resourceData.ui.mode ? resourceData.ui.mode : null,
        hits: resourceData.hits ? resourceData.hits : defaultHits,
        workbench
      });
    },

    __applyUuid: function(value, old) {
      const resourceType = this.getResourceType() || "study";
      osparc.utils.Utils.setIdToWidget(this, resourceType + "BrowserListItem_" + value);

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
      if (osparc.product.Utils.showQuality() && osparc.metadata.Quality.isEnabled(quality)) {
        const tsrRatingLayout = this.getChildControl("tsr-rating");
        const tsrRating = tsrRatingLayout.getChildren()[1];
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
        const uiModeIcon = this.getChildControl("workbench-mode");
        uiModeIcon.set({
          source,
          toolTipText,
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
        // it is a service
        return;
      }

      if (this.isResourceType("study") || this.isResourceType("template")) {
        this.setEmptyWorkbench(Object.keys(workbench).length === 0);
      }

      // Updatable study
      if (osparc.study.Utils.isWorkbenchRetired(workbench)) {
        this.setUpdatable("retired");
      } else if (osparc.study.Utils.isWorkbenchDeprecated(workbench)) {
        this.setUpdatable("deprecated");
      } else {
        const updatable = osparc.study.Utils.isWorkbenchUpdatable(workbench)
        if (updatable) {
          this.setUpdatable("updatable");
        }
      }

      // Block card
      const unaccessibleServices = osparc.study.Utils.getInaccessibleServices(workbench)
      if (unaccessibleServices.length) {
        this.setBlocked("UNKNOWN_SERVICES");
        const image = "@FontAwesome5Solid/ban/";
        let toolTipText = this.tr("Service info missing");
        unaccessibleServices.forEach(unSrv => {
          toolTipText += "<br>" + unSrv.key + ":" + unSrv.version;
        });
        this.__showBlockedCard(image, toolTipText);
      }
    },

    __applyEmptyWorkbench: function(isEmpty) {
      const emptyWorkbench = this.getChildControl("empty-workbench");
      emptyWorkbench.setVisibility(isEmpty ? "visible" : "excluded");
    },

    __applyUpdatable: function(updatable) {
      const updateStudy = this.getChildControl("update-study");
      updateStudy.addListener("pointerdown", e => e.stopPropagation());
      updateStudy.addListener("tap", e => {
        e.stopPropagation();
        this.__openUpdateServices();
      }, this);

      let toolTipText = null;
      let textColor = null;
      switch (updatable) {
        case "retired":
          toolTipText = this.tr("Service(s) retired, please update");
          textColor = osparc.service.StatusUI.getColor("retired");
          break;
        case "deprecated":
          toolTipText = this.tr("Service(s) deprecated, please update");
          textColor = osparc.service.StatusUI.getColor("deprecated");
          break;
        case "updatable":
          toolTipText = this.tr("Update available");
          textColor = "text";
          break;
      }
      if (toolTipText || textColor) {
        updateStudy.show();
        updateStudy.set({
          toolTipText,
          textColor
        });
      }
    },

    __applyState: function(state) {
      const locked = ("locked" in state) ? state["locked"]["value"] : false;
      this.setBlocked(locked ? "IN_USE" : false);
      if (locked) {
        this.__showBlockedCardFromStatus(state["locked"]);
      }

      const projectState = ("state" in state) ? state["state"]["value"] : undefined;
      if (projectState) {
        this._applyProjectState(state["state"]);
      }
    },

    _applyProjectState: function(projectStatus) {
      const status = projectStatus["value"];
      let icon;
      let toolTip;
      let border;
      switch (status) {
        case "STARTED":
          icon = "@FontAwesome5Solid/spinner/10";
          toolTip = this.tr("Running");
          border = "info";
          break;
        case "SUCCESS":
          icon = "@FontAwesome5Solid/check/10";
          toolTip = this.tr("Ran successfully");
          border = "success";
          break;
        case "ABORTED":
          icon = "@FontAwesome5Solid/exclamation/10";
          toolTip = this.tr("Run aborted");
          border = "warning";
          break;
        case "FAILED":
          icon = "@FontAwesome5Solid/exclamation/10";
          toolTip = this.tr("Ran with error");
          border = "error";
          break;
        default:
          icon = null;
          toolTip = null;
          border = null;
          break;
      }
      this.__applyProjectLabel(icon, toolTip, border);
    },

    __applyProjectLabel: function(icn, toolTipText, bdr) {
      const border = new qx.ui.decoration.Decorator().set({
        radius: 10,
        width: 1,
        style: "solid",
        color: bdr,
        backgroundColor: bdr ? bdr + "-bg" : null
      });
      const projectStatusLabel = this.getChildControl("project-status");
      projectStatusLabel.set({
        decorator: border,
        textColor: bdr,
        alignX: "center",
        alignY: "middle",
        height: 17,
        width: 17,
        padding: 3
      });

      projectStatusLabel.set({
        visibility: icn && toolTipText && bdr ? "visible" : "excluded",
        source: icn,
        toolTipIcon: icn,
        toolTipText
      });
    },

    __showBlockedCardFromStatus: function(lockedStatus) {
      const status = lockedStatus["status"];
      const owner = lockedStatus["owner"];
      let toolTip = osparc.utils.Utils.firstsUp(owner["first_name"] || this.tr("A user"), owner["last_name"] || "");
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
          image = osparc.task.Export.ICON+"/";
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
      this.__showBlockedCard(image, toolTip);
    },

    __showBlockedCard: function(lockImageSrc, toolTipText) {
      this.getChildControl("lock-status").set({
        opacity: 1.0,
        visibility: "visible"
      });
      const lockImage = this.getChildControl("lock-status").getChildControl("image");
      lockImageSrc += this.classname.includes("Grid") ? "32" : "22";
      lockImage.setSource(lockImageSrc);
      if (toolTipText) {
        this.set({
          toolTipText
        });
      }
    },

    __applyBlocked: function(blocked) {
      const enabled = !blocked;
      if (enabled) {
        this.resetToolTipText();
      }

      this._getChildren().forEach(item => {
        if (item && "setOpacity" in item) {
          item.setOpacity(enabled ? 1.0 : 0.7);
        }
      });

      this.getChildControl("lock-status").set({
        appearance: "form-button-outlined/disabled",
        textColor: "text-disabled",
        opacity: 1.0,
        visibility: enabled ? "excluded" : "visible"
      });

      // let the "pointer" cursor for IN_USE or UNKNOWN_SERVICE
      this.set({
        cursor: blocked === true ? "not-allowed" : "pointer"
      });

      [
        "tick-selected",
        "tick-unselected",
        // "menu-button"
      ].forEach(childName => {
        const child = this.getChildControl(childName);
        child.setEnabled(enabled);
      });

      this.evaluateMenuButtons();
    },

    evaluateMenuButtons: function() {
      if (this.getMenu()) {
        const menuButtons = this.getMenu().getChildren();
        const resourceData = this.getResourceData();

        const openButton = menuButtons.find(menuBtn => "openResourceButton" in menuBtn);
        if (openButton) {
          openButton.setEnabled(osparc.study.Utils.canBeOpened(resourceData));
        }
        const duplicateButton = menuButtons.find(menuBtn => "duplicateButton" in menuBtn);
        if (duplicateButton) {
          duplicateButton.setEnabled(osparc.study.Utils.canBeDuplicated(resourceData));
        }
        const exportCMISButton = menuButtons.find(menuBtn => "exportCMISButton" in menuBtn);
        if (exportCMISButton) {
          exportCMISButton.setEnabled(osparc.study.Utils.canBeExported(resourceData));
        }
        const studyDataButton = menuButtons.find(menuBtn => "studyDataButton" in menuBtn);
        if (studyDataButton) {
          studyDataButton.setEnabled(osparc.study.Utils.canShowStudyData(resourceData));
        }
        const billingSettingsButton = menuButtons.find(menuBtn => "billingSettingsButton" in menuBtn);
        if (billingSettingsButton) {
          billingSettingsButton.setEnabled(osparc.study.Utils.canShowBillingOptions(resourceData));
        }
        const moveToButton = menuButtons.find(menuBtn => "moveToButton" in menuBtn);
        if (moveToButton) {
          moveToButton.setEnabled(osparc.study.Utils.canMoveTo(resourceData));
        }
        const trashButton = menuButtons.find(menuBtn => "trashButton" in menuBtn);
        if (trashButton) {
          trashButton.setEnabled(osparc.study.Utils.canBeDeleted(resourceData));
        }
      }
    },

    _applyFetching: function(value) {
      throw new Error("Abstract method called!");
    },

    _applyMenu: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _setStudyPermissions: function(accessRights) {
      const permissionIcon = this.getChildControl("permission-icon");
      if (osparc.data.model.Study.canIWrite(accessRights)) {
        permissionIcon.exclude();
      } else {
        permissionIcon.show();
      }
    },

    __openMoreOptions: function() {
      const resourceData = this.getResourceData();
      const resourceDetails = new osparc.dashboard.ResourceDetails(resourceData);
      const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
      [
        "updateStudy",
        "updateTemplate",
        "updateService"
      ].forEach(ev => {
        resourceDetails.addListener(ev, e => this.fireDataEvent(ev, e.getData()));
      });
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
      return resourceDetails;
    },

    _startStudyById: function(studyId, openCB, cancelCB, isStudyCreation = false) {
      osparc.dashboard.ResourceBrowserBase.startStudyById(studyId, openCB, cancelCB, isStudyCreation);
    },

    openData: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openData();
    },

    openBilling: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openBillingSettings();
    },

    openAccessRights: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openAccessRights();
    },

    openTags: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openTags();
    },

    __openQualityEditor: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openQuality();
    },

    __openUpdateServices: function() {
      const moreOpts = this.__openMoreOptions();
      moreOpts.openUpdateServices();
    },

    _getEmptyWorkbenchIcon: function() {
      let toolTipText = this.tr("Empty") + " ";
      if (this.isResourceType("study")) {
        toolTipText += osparc.product.Utils.getStudyAlias();
      } else if (this.isResourceType("template")) {
        toolTipText += osparc.product.Utils.getTemplateAlias();
      }
      const control = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/times-circle/14",
        alignY: "bottom",
        toolTipText
      });
      control.addListener("tap", e => {
        e.stopPropagation();
        this.setValue(false);
        this.fireDataEvent("emptyStudyClicked", this.getUuid());
      }, this);
      return control;
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
        this.getUuid(),
        this.getTitle(),
        this.getDescription(),
        this.getOwner()
      ];
      return this.self().filterText(checks, text);
    },

    _filterTags: function(tags) {
      const checks = this.getTags().map(tag => tag.getTagId());
      return this.self().filterTags(checks, tags);
    },

    _filterSharedWith: function(sharedWith) {
      const checks = this.getAccessRights();
      return this.self().filterSharedWith(checks, sharedWith);
    },

    _filterServiceType: function(serviceType) {
      const resourceType = this.getResourceType();
      const resourceData = this.getResourceData();
      return this.self().filterServiceType(resourceType, resourceData, serviceType);
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
      if (this._filterSharedWith(data.sharedWith)) {
        return true;
      }
      if (this._filterServiceType(data.serviceType)) {
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
      if (data.sharedWith) {
        return true;
      }
      if ("serviceType" in data) {
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
