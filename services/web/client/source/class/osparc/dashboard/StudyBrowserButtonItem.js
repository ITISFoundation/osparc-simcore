/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.StudyBrowserButtonItem", {
  extend: osparc.dashboard.StudyBrowserButtonBase,

  construct: function() {
    this.base(arguments);

    this.addListener("changeValue", this.__itemSelected, this);
  },

  properties: {
    resourceData: {
      check: "Object",
      nullable: false,
      apply: "__applyResourceData"
    },

    resourceType: {
      check: ["study", "template", "service"],
      nullable: false,
      event: "changeResourceType"
    },

    menu: {
      check: "qx.ui.menu.Menu",
      nullable: true,
      apply: "_applyMenu",
      event: "changeMenu"
    },

    uuid: {
      check: "String",
      apply: "_applyUuid"
    },

    studyTitle: {
      check: "String",
      apply: "_applyStudyTitle",
      nullable: true
    },

    studyDescription: {
      check: "String",
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
      apply: "_applyQuality"
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

    multiSelectionMode: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyMultiSelectionMode"
    }
  },

  events: {
    "updateQualityStudy": "qx.event.type.Data",
    "updateQualityTemplate": "qx.event.type.Data",
    "updateQualityService": "qx.event.type.Data"
  },

  statics: {
    MENU_BTN_WIDTH: 25,
    SHARED_USER: "@FontAwesome5Solid/user/14",
    SHARED_ORGS: "@FontAwesome5Solid/users/14",
    SHARED_ALL: "@FontAwesome5Solid/globe/14",
    STUDY_ICON: "@FontAwesome5Solid/file-alt/50",
    TEMPLATE_ICON: "@FontAwesome5Solid/copy/50",
    SERVICE_ICON: "@FontAwesome5Solid/paw/50",
    PERM_READ: "@FontAwesome5Solid/eye/16",
    PERM_WRITE: "@FontAwesome5Solid/edit/16",
    PERM_EXECUTE: "@FontAwesome5Solid/crown/16"
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "menu-button":
          control = new qx.ui.form.MenuButton().set({
            width: this.self().MENU_BTN_WIDTH,
            height: this.self().MENU_BTN_WIDTH,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._add(control, {
            top: -2,
            right: -2
          });
          break;
        case "tick-unselected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/16");
          this._add(control, {
            top: 4,
            right: 4
          });
          break;
        case "tick-selected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check-circle/16");
          this._add(control, {
            top: 4,
            right: 4
          });
          break;
        case "lock-status":
          control = new osparc.ui.basic.Thumbnail();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "exporting": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
            alignX: "center",
            alignY: "middle"
          }));
          // const icon = new osparc.ui.basic.Thumbnail("@FontAwesome5Solid/file-export/60");
          const icon = new osparc.ui.basic.Thumbnail("@FontAwesome5Solid/cloud-download-alt/60");
          control.add(icon, {
            flex: 1
          });
          const label = new qx.ui.basic.Label(this.tr("Exporting..."));
          control.add(label);
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        }
        case "permission-icon": {
          control = new qx.ui.basic.Image();
          control.exclude();
          this._add(control, {
            bottom: 2,
            right: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    isResourceType: function(resourceType) {
      return this.getResourceType() === resourceType;
    },

    _applyMultiSelectionMode: function(value) {
      if (value) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("excluded");
        this.__itemSelected();
      } else {
        this.__showMenuOnly();
      }
    },

    __applyResourceData: function(studyData) {
      let defaultThumbnail = "";
      let uuid = null;
      let owner = "";
      let accessRights = {};
      switch (studyData["resourceType"]) {
        case "study":
          uuid = studyData.uuid ? studyData.uuid : uuid;
          owner = studyData.prjOwner ? studyData.prjOwner : owner;
          accessRights = studyData.accessRights ? studyData.accessRights : accessRights;
          defaultThumbnail = this.self().STUDY_ICON;
          break;
        case "template":
          uuid = studyData.uuid ? studyData.uuid : uuid;
          owner = studyData.prjOwner ? studyData.prjOwner : owner;
          accessRights = studyData.accessRights ? studyData.accessRights : accessRights;
          defaultThumbnail = this.self().TEMPLATE_ICON;
          break;
        case "service":
          uuid = studyData.key ? studyData.key : uuid;
          owner = studyData.owner ? studyData.owner : owner;
          accessRights = studyData.access_rights ? studyData.access_rights : accessRights;
          defaultThumbnail = this.self().SERVICE_ICON;
          break;
      }

      this.set({
        resourceType: studyData.resourceType,
        uuid,
        studyTitle: studyData.name,
        studyDescription: studyData.description,
        owner,
        accessRights,
        lastChangeDate: studyData.lastChangeDate ? new Date(studyData.lastChangeDate) : null,
        icon: studyData.thumbnail || defaultThumbnail,
        state: studyData.state ? studyData.state : {},
        classifiers: studyData.classifiers && studyData.classifiers ? studyData.classifiers : [],
        quality: studyData.quality ? studyData.quality : null
      });
    },

    __itemSelected: function() {
      if (this.isResourceType("study")) {
        const selected = this.getValue();

        if (this.isLocked() && selected) {
          this.setValue(false);
        }

        const tick = this.getChildControl("tick-selected");
        tick.setVisibility(selected ? "visible" : "excluded");

        const untick = this.getChildControl("tick-unselected");
        untick.setVisibility(selected ? "excluded" : "visible");
      } else {
        this.__showMenuOnly();
      }
    },

    __showMenuOnly: function() {
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility("visible");
      const tick = this.getChildControl("tick-selected");
      tick.setVisibility("excluded");
      const untick = this.getChildControl("tick-unselected");
      untick.setVisibility("excluded");
    },

    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    },

    _applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);
    },

    _applyStudyTitle: function(value, old) {
      const label = this.getChildControl("title");
      label.setValue(value);
      label.addListener("appear", () => {
        qx.event.Timer.once(() => {
          const labelDom = label.getContentElement().getDomElement();
          if (label.getMaxWidth() === parseInt(labelDom.style.width)) {
            label.setToolTipText(value);
          }
        }, this, 50);
      });
    },

    _applyLastChangeDate: function(value, old) {
      if (value && this.isResourceType("study")) {
        const label = this.getChildControl("subtitle-text");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    _applyOwner: function(value, old) {
      if (this.isResourceType("service") || this.isResourceType("template")) {
        const label = this.getChildControl("subtitle-text");
        label.setValue(value);
      }
    },

    _applyAccessRights: function(value, old) {
      if (value && Object.keys(value).length) {
        const sharedIcon = this.getChildControl("subtitle-icon");

        const store = osparc.store.Store.getInstance();
        Promise.all([
          store.getGroupsAll(),
          store.getVisibleMembers(),
          store.getGroupsOrganizations()
        ])
          .then(values => {
            const all = values[0];
            const orgMembs = [];
            const orgMembers = values[1];
            for (const gid of Object.keys(orgMembers)) {
              orgMembs.push(orgMembers[gid]);
            }
            const orgs = values.length === 3 ? values[2] : [];
            const groups = [orgMembs, orgs, [all]];
            this.__setSharedIcon(sharedIcon, value, groups);
          });

        if (this.isResourceType("study")) {
          this.__setStudyPermissions(value);
        }
      }
    },

    __setSharedIcon: function(image, value, groups) {
      let sharedGrps = [];
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      for (let i=0; i<groups.length; i++) {
        const sharedGrp = [];
        const gids = Object.keys(value);
        for (let j=0; j<gids.length; j++) {
          const gid = parseInt(gids[j]);
          if (this.isResourceType("study") && (gid === myGroupId)) {
            continue;
          }
          const grp = groups[i].find(group => group["gid"] === gid);
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
            image.setSource(this.self().SHARED_USER);
            break;
          case 1:
            image.setSource(this.self().SHARED_ORGS);
            break;
          case 2:
            image.setSource(this.self().SHARED_ALL);
            break;
        }
      }

      if (sharedGrps.length === 0) {
        image.setVisibility("excluded");
        return;
      }

      const sharedGrpLabels = [];
      const maxItems = 6;
      for (let i=0; i<sharedGrps.length; i++) {
        if (i > maxItems) {
          sharedGrpLabels.push("...");
          break;
        }
        const sharedGrpLabel = sharedGrps[i]["label"];
        if (!sharedGrpLabels.includes(sharedGrpLabel)) {
          sharedGrpLabels.push(sharedGrpLabel);
        }
      }
      const hintText = sharedGrpLabels.join("<br>");
      const hint = new osparc.ui.hint.Hint(image, hintText);
      image.addListener("mouseover", () => hint.show(), this);
      image.addListener("mouseout", () => hint.exclude(), this);
    },

    _applyTags: function(tags) {
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        const tagsContainer = this.getChildControl("tags");
        tagsContainer.removeAll();
        tags.forEach(tag => {
          const tagUI = new osparc.ui.basic.Tag(tag.name, tag.color, "sideSearchFilter");
          tagUI.setFont("text-12");
          tagsContainer.add(tagUI);
        });
      }
    },

    _applyQuality: function(quality) {
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

    __setStudyPermissions: function(accessRights) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
      orgIDs.push(myGroupId);

      const image = this.getChildControl("permission-icon");
      if (osparc.component.permissions.Study.canGroupsWrite(accessRights, orgIDs)) {
        image.exclude();
      } else {
        image.setSource(this.self().PERM_READ);
      }

      this.addListener("mouseover", () => image.show(), this);
      this.addListener("mouseout", () => image.exclude(), this);
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
      const lock = this.getChildControl("lock-status");
      const lockImage = this.getChildControl("lock-status").getChildControl("image");
      let toolTipText = osparc.utils.Utils.firstsUp(owner["first_name"], owner["last_name"]);
      let source = null;
      switch (status) {
        case "CLOSING":
          source = "@FontAwesome5Solid/key/70";
          toolTipText += this.tr(" is closing it...");
          break;
        case "CLONING":
          source = "@FontAwesome5Solid/clone/70";
          toolTipText += this.tr(" is cloning it...");
          break;
        case "EXPORTING":
          source = osparc.component.task.Export.EXPORT_ICON+"/70";
          toolTipText += this.tr(" is exporting it...");
          break;
        case "OPENING":
          source = "@FontAwesome5Solid/key/70";
          toolTipText += this.tr(" is opening it...");
          break;
        case "OPENED":
          source = "@FontAwesome5Solid/lock/70";
          toolTipText += this.tr(" is using it.");
          break;
        default:
          source = "@FontAwesome5Solid/lock/70";
          break;
      }
      lock.set({
        toolTipText: toolTipText
      });
      lockImage.setSource(source);
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

    setExporting: function(exporting) {
      this.__enableCard(!exporting);

      const icon = this.getChildControl("exporting");
      icon.set({
        opacity: 1.0,
        visibility: exporting ? "visible" : "excluded"
      });
    },

    setImporting: function(importing) {
      this.__enableCard(!importing);

      const icon = this.getChildControl("importing");
      icon.set({
        opacity: 1.0,
        visibility: importing ? "visible" : "excluded"
      });
    },

    __openQualityEditor: function() {
      const resourceData = this.getResourceData();
      const qualityEditor = osparc.studycard.Utils.openQuality(resourceData);
      qualityEditor.addListener("updateQuality", e => {
        const updatedResourceData = e.getData();
        if (osparc.utils.Resources.isStudy(resourceData)) {
          this.fireDataEvent("updateQualityStudy", updatedResourceData);
        } else if (osparc.utils.Resources.isTemplate(resourceData)) {
          this.fireDataEvent("updateQualityTemplate", updatedResourceData);
        } else if (osparc.utils.Resources.isService(resourceData)) {
          this.fireDataEvent("updateQualityService", updatedResourceData);
        }
      });
    },

    __filterText: function(text) {
      if (text) {
        const checks = [
          this.getStudyTitle(),
          this.getOwner()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(text)).length == 0) {
          return true;
        }
      }
      return false;
    },

    __filterTags: function(tags) {
      if (tags && tags.length) {
        const tagNames = this.getTags().map(tag => tag.name);
        if (tags.filter(tag => tagNames.includes(tag)).length == 0) {
          return true;
        }
      }
      return false;
    },

    __filterClassifiers: function(classifiers) {
      if (classifiers && classifiers.length) {
        const classes = osparc.utils.Classifiers.getLeafClassifiers(classifiers);
        const myClassifiers = this.getClassifiers();
        if (classes.filter(clas => myClassifiers.includes(clas.data.classifier)).length == 0) {
          return true;
        }
      }
      return false;
    },

    _shouldApplyFilter: function(data) {
      if (this.__filterText(data.text)) {
        return true;
      }
      if (this.__filterTags(data.tags)) {
        return true;
      }
      if (this.__filterClassifiers(data.classifiers)) {
        return true;
      }
      return false;
    }
  }
});
