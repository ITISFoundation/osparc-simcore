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
  extend: qx.ui.core.Widget,
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

    this.addListener("changeSelected", this.__evalSelectedButton, this);
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateTutorial": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "updateHypertool": "qx.event.type.Data",
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
    PRODUCT_ICON: osparc.product.Utils.getIconUrl(),
    // Get the default thumbnail for each product else add the image and extension osparc.product.Utils.getThumbnailUrl(Thumbnail-01.png)
    PRODUCT_THUMBNAIL: osparc.product.Utils.getThumbnailUrl(),

    CARD_PRIORITY: {
      NEW: 0,
      PLACEHOLDER: 1,
      ITEM: 2,
      LOADER: 3
    },

    ICON_SIZE: 32,

    createCardIcon: function() {
      const iconSize = osparc.dashboard.CardBase.ICON_SIZE;
      const icon = new osparc.ui.basic.Thumbnail(null, iconSize, iconSize).set({
        minHeight: iconSize,
        minWidth: iconSize,
      });
      icon.getChildControl("image").set({
        anonymous: true,
        decorator: "rounded",
        minWidth: iconSize,
        minHeight: iconSize,
      });
      return icon
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
        const includesSome = checks.some(check => check && check.toLowerCase().trim().includes(text.toLowerCase()));
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
      if (sharedWith && checks) {
        const groupsStore = osparc.store.Groups.getInstance();
        const myGroupId = groupsStore.getMyGroupId();

        switch (sharedWith) {
          case "show-all":
            return false;
          case "my-resources": {
            if (myGroupId in checks) {
              const myAccessRights = checks[myGroupId];
              const totalAccess = "delete" in myAccessRights ? myAccessRights["delete"] : myAccessRights["write"];
              // show those that I have ownership of: have explicit delete (study/template) or write (service) access
              return !totalAccess;
            }
            return true;
          }
          case "shared-with-me": {
            if (myGroupId in checks) {
              const myAccessRights = checks[myGroupId];
              const totalAccess = "delete" in myAccessRights ? myAccessRights["delete"] : myAccessRights["write"];
              // hide those that I'm ownership of: have explicit and delete (study/template) or write (service) access
              return totalAccess;
            }
            // if we get here, it means that it was shared-with-me via an organization
            return false;
          }
          case "shared-with-everyone": {
            const everyoneGroupIds = [
              groupsStore.getEveryoneProductGroup().getGroupId(),
              groupsStore.getEveryoneGroup().getGroupId(),
            ];
            const found = Object.keys(checks).some(gId => everyoneGroupIds.includes(parseInt(gId)));
            // show those that are shared with "1" or product everyone's groupId
            return !found;
          }
          default:
            return true;
        }
      }
      return false;
    },

    filterAppType: function(resourceType, metadata, appType) {
      if (appType) {
        if (resourceType === "service" && metadata && metadata.type) {
          const matches = (metadata.type === appType);
          return !matches;
        } else if (resourceType === "hypertool") {
          const matches = (resourceType === appType);
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

    populateShareIcon: function(shareIcon, accessRights) {
      const gids = Object.keys(accessRights).map(key => parseInt(key));

      // Icon
      const groupsStore = osparc.store.Groups.getInstance();
      const groupEveryone = groupsStore.getEveryoneGroup();
      const groupProductEveryone = groupsStore.getEveryoneProductGroup();
      const organizations = groupsStore.getOrganizations();
      const myGroupId = groupsStore.getMyGroupId();

      const organizationIds = Object.keys(organizations).map(key => parseInt(key));
      if (gids.includes(groupEveryone.getGroupId()) || gids.includes(groupProductEveryone.getGroupId())) {
        shareIcon.setSource(osparc.dashboard.CardBase.SHARED_ALL);
      } else if (organizationIds.filter(value => gids.includes(value)).length) { // find intersection
        shareIcon.setSource(osparc.dashboard.CardBase.SHARED_ORGS);
      } else if (gids.length === 1 && gids[0] === myGroupId) {
        shareIcon.setSource(osparc.dashboard.CardBase.SHARE_ICON);
      } else {
        shareIcon.setSource(osparc.dashboard.CardBase.SHARED_USER);
      }

      // Tooltip
      if (gids.length === 0 || (gids.length === 1 && gids[0] === myGroupId)) {
        const canIWrite = osparc.data.model.Study.canIWrite(accessRights);
        if (canIWrite) {
          shareIcon.set({
            toolTipText: qx.locale.Manager.tr("Share")
          });
        }
        return;
      }

      this.addHintFromGids(shareIcon, gids);
    },

    addHintFromGids: function(icon, gids) {
      const groupsStore = osparc.store.Groups.getInstance();
      const groupEveryone = groupsStore.getEveryoneGroup();
      const groupProductEveryone = groupsStore.getEveryoneProductGroup();
      const organizations = groupsStore.getOrganizations();
      const myGroupId = groupsStore.getMyGroupId();

      const groups = [];
      groups.push(groupEveryone);
      groups.push(groupProductEveryone);
      groups.push(...Object.values(organizations));
      const sharedGrps = [];
      groups.forEach(group => {
        const idx = gids.indexOf(group.getGroupId());
        if (idx > -1) {
          sharedGrps.push(group);
          gids.splice(idx, 1);
        }
      });

      const hint = new osparc.ui.hint.Hint(icon);
      icon.addListener("mouseover", async () => {
        hint.show();

        // lazy load tooltip, this can be an expensive call

        // once the groups were removed, the remaining group ids are users' primary groups ids
        const usersStore = osparc.store.Users.getInstance();
        for (let i=0; i<gids.length; i++) {
          const gid = gids[i];
          if (myGroupId !== gid) {
            const user = await usersStore.getUser(gid);
            if (user) {
              sharedGrps.push(user);
            }
          }
        }

        if (hint.getText() === "") {
          const sharedGrpLabels = [];
          const maxItems = 6;
          for (let i=0; i<sharedGrps.length; i++) {
            if (i > maxItems) {
              sharedGrpLabels.push("...");
              break;
            }
            let sharedGrpLabel = sharedGrps[i].getLabel();
            if ([groupEveryone, groupProductEveryone].includes(sharedGrps[i])) {
              sharedGrpLabel = "Public";
            }
            if (!sharedGrpLabels.includes(sharedGrpLabel)) {
              sharedGrpLabels.push(sharedGrpLabel);
            }
          }
          const hintText = sharedGrpLabels.join("<br>");
          if (hintText) {
            hint.setText(hintText);
          }
        }
      }, this);
      icon.addListener("mouseout", () => hint.exclude(), this);
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

    selected: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeSelected",
    },

    icon: {
      check: "String",
      init: null,
      nullable: true,
      apply: "_applyIcon",
    },

    thumbnail: {
      check: "String",
      init: null,
      nullable: true,
      apply: "_applyThumbnail",
    },

    resourceData: {
      check: "Object",
      nullable: false,
      init: null,
      apply: "__applyResourceData"
    },

    resourceType: {
      check: [
        "study",
        "template",
        "tutorial",
        "hypertool",
        "service",
      ],
      init: true,
      nullable: true,
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

    trashedAt: {
      check: "Date",
      apply: "_applyTrashedAt",
      nullable: true
    },

    trashedBy: {
      check: "Number",
      apply: "_applyTrashedBy",
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
    },

    services: {
      check: "Array",
      init: true,
      nullable: false,
      apply: "__applyServices",
      event: "changeServices",
    },

    uiMode: {
      check: [
        "workbench", // =auto, the frontend decides the icon and default view
        "app", "guided", // "guided" is no longer used
        "standalone",
        "pipeline",
      ],
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

    debt: {
      check: "Number",
      nullable: true,
      init: 0,
      apply: "__applyDebt"
    },

    blocked: {
      check: [true, "UNKNOWN_SERVICES", "IN_USE", "IN_DEBT", false],
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
      apply: "__applyMultiSelectionMode"
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
      let icon = null;
      switch (resourceData["resourceType"]) {
        case "study":
        case "template":
        case "tutorial":
        case "hypertool":
          uuid = resourceData.uuid ? resourceData.uuid : null;
          owner = resourceData.prjOwner ? resourceData.prjOwner : "";
          workbench = resourceData.workbench ? resourceData.workbench : {};
          break;
        case "service":
          uuid = resourceData.key ? resourceData.key : null;
          owner = resourceData.owner ? resourceData.owner : resourceData.contact;
          icon = resourceData["icon"] || osparc.dashboard.CardBase.PRODUCT_ICON;
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
        trashedAt: resourceData.trashedAt ? new Date(resourceData.trashedAt) : null,
        trashedBy: resourceData.trashedBy || null,
        icon,
        thumbnail: resourceData.thumbnail || this.self().PRODUCT_THUMBNAIL,
        state: resourceData.state ? resourceData.state : {},
        classifiers: resourceData.classifiers && resourceData.classifiers ? resourceData.classifiers : [],
        quality: resourceData.quality ? resourceData.quality : null,
        uiMode: resourceData.ui && resourceData.ui.mode ? resourceData.ui.mode : null,
        hits: resourceData.hits ? resourceData.hits : defaultHits,
        workbench
      });

      if ([
        "study",
        "template",
        "tutorial",
        "hypertool"
      ].includes(resourceData["resourceType"])) {
        osparc.store.Services.getStudyServices(resourceData.uuid)
          .then(resp => {
            const services = resp["services"];
            resourceData["services"] = services;
            this.setServices(services);
          })
          .catch(err => console.error(err));

        osparc.study.Utils.guessIcon(resourceData)
          .then(iconSource => this.setIcon(iconSource));
      }
    },

    __applyMultiSelectionMode: function(value) {
      if (!value) {
        this.setSelected(false);
      }
      this.__evalSelectedButton();
    },

    __evalSelectedButton: function() {
      if (
        this.hasChildControl("menu-selection-stack") &&
        this.hasChildControl("menu-button") &&
        this.hasChildControl("tick-selected") &&
        this.hasChildControl("tick-unselected")
      ) {
        const menuButtonStack = this.getChildControl("menu-selection-stack");
        if (this.isResourceType("study") && this.isMultiSelectionMode()) {
          const tick = this.getChildControl("tick-selected");
          const untick = this.getChildControl("tick-unselected");
          const selected = this.getSelected();
          menuButtonStack.setSelection(selected ? [tick] : [untick]);
        } else {
          const menuButton = this.getChildControl("menu-button");
          menuButtonStack.setSelection([menuButton]);
        }
      }
    },

    __applyUuid: function(value, old) {
      const resourceType = this.getResourceType() || "study";
      osparc.utils.Utils.setIdToWidget(this, resourceType + "BrowserListItem_" + value);

      this.setCardKey(value);
    },

    _applyIcon: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyThumbnail: function(value, old) {
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

    _applyTrashedAt: function(value, old) {
      throw new Error("Abstract method called!");
    },

    _applyTrashedBy: function(value, old) {
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
      switch (uiMode) {
        case "guided":
        case "app": {
          const uiModeIcon = this.getChildControl("workbench-mode");
          uiModeIcon.set({
            source: osparc.dashboard.CardBase.MODE_APP,
            toolTipText: this.tr("App mode"),
          });
          break;
        }
      }
    },

    __applyHits: function(hits) {
      if (hits !== null) {
        const hitsLabel = this.getChildControl("hits-service");
        hitsLabel.setValue(this.tr("Hits: ") + String(hits));
      }
    },

    __applyServices: function(services) {
      this.setEmptyWorkbench(services.length === 0);

      // Updatable study
      if (osparc.study.Utils.anyServiceRetired(services)) {
        this.setUpdatable("retired");
      } else if (osparc.study.Utils.anyServiceDeprecated(services)) {
        this.setUpdatable("deprecated");
      } else if (osparc.study.Utils.anyServiceUpdatable(services)) {
        this.setUpdatable("updatable");
      }

      // Block card
      const cantReadServices = osparc.study.Utils.getCantExecuteServices(services);
      if (cantReadServices.length) {
        this.setBlocked("UNKNOWN_SERVICES");
        const image = "@FontAwesome5Solid/ban/";
        let toolTipText = this.tr("Inaccessible service(s):");
        cantReadServices.forEach(unSrv => {
          toolTipText += "<br>" + unSrv.key + ":" + osparc.service.Utils.extractVersionDisplay(unSrv.release);
        });
        this.__showBlockedCard(image, toolTipText);
      }

      this.evaluateMenuButtons();
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
      let lockInUse = false;
      if ("locked" in state && "value" in state["locked"]) {
        lockInUse = state["locked"]["value"];
      }
      this.setBlocked(lockInUse ? "IN_USE" : false);
      if (lockInUse) {
        this.__showBlockedCardFromStatus("IN_USE", state["locked"]);
      }

      const pipelineState = ("state" in state) ? state["state"]["value"] : undefined;
      if (pipelineState) {
        this.__applyPipelineState(state["state"]["value"]);
      }
    },

    __applyDebt: function(debt) {
      this.setBlocked(debt ? "IN_DEBT" : false);
      if (debt) {
        this.__showBlockedCardFromStatus("IN_DEBT", debt);
      }
    },

    // pipelineState: ["NOT_STARTED", "STARTED", "SUCCESS", "ABORTED", "FAILED", "UNKNOWN"]
    __applyPipelineState: function(pipelineState) {
      let iconSource;
      let toolTipText;
      let borderColor;
      switch (pipelineState) {
        case "STARTED":
          iconSource = "@FontAwesome5Solid/spinner/10";
          toolTipText = this.tr("Running");
          borderColor = "info";
          break;
        case "SUCCESS":
          iconSource = "@FontAwesome5Solid/check/10";
          toolTipText = this.tr("Ran successfully");
          borderColor = "success";
          break;
        case "ABORTED":
          iconSource = "@FontAwesome5Solid/exclamation/10";
          toolTipText = this.tr("Run aborted");
          borderColor = "warning";
          break;
        case "FAILED":
          iconSource = "@FontAwesome5Solid/exclamation/10";
          toolTipText = this.tr("Unsuccessful Run");
          borderColor = "error";
          break;
        case "UNKNOWN":
        case "NOT_STARTED":
        default:
          iconSource = null;
          toolTipText = null;
          borderColor = null;
          break;
      }

      const border = new qx.ui.decoration.Decorator().set({
        radius: 10,
        width: 1,
        style: "solid",
        color: borderColor,
        backgroundColor: borderColor ? borderColor + "-bg" : null
      });

      const projectStatusLabel = this.getChildControl("project-status");
      projectStatusLabel.set({
        decorator: border,
        textColor: borderColor,
        alignX: "center",
        alignY: "middle",
        height: 17,
        width: 17,
        padding: 3
      });

      projectStatusLabel.set({
        visibility: iconSource && toolTipText && borderColor ? "visible" : "excluded",
        source: iconSource,
        toolTipIcon: iconSource,
        toolTipText
      });
    },

    __showBlockedCardFromStatus: function(reason, moreInfo) {
      switch (reason) {
        case "IN_USE":
          this.__blockedInUse(moreInfo);
          break;
        case "IN_DEBT":
          this.__blockedInDebt(moreInfo);
          break;
      }
    },

    __blockedInUse: function(lockedStatus) {
      const status = lockedStatus["status"];
      const owner = lockedStatus["owner"];
      let toolTip = osparc.utils.Utils.firstsUp(owner["first_name"] || this.tr("A user"), owner["last_name"] || ""); // it will be replaced by "userName"
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

    __blockedInDebt: function() {
      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      const toolTip = studyAlias + " " + this.tr("Embargoed<br>Credits Required");
      const image = "@FontAwesome5Solid/lock/";
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
        const convertToPipelineButton = menuButtons.find(menuBtn => "convertToPipelineButton" in menuBtn);
        if (convertToPipelineButton) {
          convertToPipelineButton.setEnabled(osparc.study.Utils.canBeDuplicated(resourceData));
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

    __openResourceDetails: function(openWindowCB) {
      const resourceData = this.getResourceData();
      const resourceDetails = new osparc.dashboard.ResourceDetails(resourceData);
      resourceDetails.addListenerOnce("pagesAdded", () => {
        if (openWindowCB in resourceDetails) {
          resourceDetails[openWindowCB]();
        }
      })
      const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
      [
        "updateStudy",
        "updateTemplate",
        "updateTutorial",
        "updateService",
        "updateHypertool",
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
      const resourceData = this.getResourceData();
      osparc.widget.StudyDataManager.popUpInWindow(resourceData["uuid"]);
    },

    openBilling: function() {
      this.__openResourceDetails("openBillingSettings");
    },

    openAccessRights: function() {
      this.__openResourceDetails("openAccessRights");
    },

    openTags: function() {
      this.__openResourceDetails("openTags");
    },

    __openQualityEditor: function() {
      this.__openResourceDetails("openQuality");
    },

    __openUpdateServices: function() {
      this.__openResourceDetails("openUpdateServices");
    },

    _getEmptyWorkbenchIcon: function() {
      let toolTipText = this.tr("Empty") + " ";
      if (this.isResourceType("study")) {
        toolTipText += osparc.product.Utils.getStudyAlias();
      } else if (this.isResourceType("template")) {
        toolTipText += osparc.product.Utils.getTemplateAlias();
      } else if (this.isResourceType("tutorial")) {
        toolTipText += osparc.product.Utils.getTutorialAlias();
      } else if (this.isResourceType("hypertool")) {
        toolTipText += osparc.product.Utils.getAppAlias();
      }
      const control = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/times-circle/14",
        alignY: "bottom",
        toolTipText
      });
      control.addListener("tap", e => {
        e.stopPropagation();
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

    __filterAppType: function(appType) {
      const resourceType = this.getResourceType();
      const resourceData = this.getResourceData();
      return this.self().filterAppType(resourceType, resourceData, appType);
    },

    _filterClassifiers: function(classifiers) {
      const checks = this.getClassifiers();
      return this.self().filterClassifiers(checks, classifiers);
    },

    __curateFilterId: function(filterId) {
      if (this.isPropertyInitialized("resourceType")) {
        switch (this.getResourceType()) {
          case "tutorial":
            filterId += "-template";
            break;
          case "hypertool":
            filterId += "-service";
            break;
          default:
            filterId += "-" + this.getResourceType();
            break;
        }
      }
      return filterId;
    },

    _shouldApplyFilter: function(data) {
      const filterId = this.__curateFilterId("searchBarFilter");
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
      if (this.__filterAppType(data.appType)) {
        return true;
      }
      if (this._filterClassifiers(data.classifiers)) {
        return true;
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      const filterId = this.__curateFilterId("searchBarFilter");
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
      if ("appType" in data) {
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
