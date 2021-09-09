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
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.ListButtonItem", {
  extend: qx.ui.form.ToggleButton,
  implement : [qx.ui.form.IModel, osparc.component.filter.IFilterable],
  include : [qx.ui.form.MModelProperty, osparc.component.filter.MFilterable],

  construct: function() {
    this.base(arguments);
    this.set({
      width: 1000,
      height: 40,
      allowGrowX: true
    });

    this._setLayout(new qx.ui.layout.HBox(10));

    [
      "pointerover",
      "focus"
    ].forEach(e => this.addListener(e, this._onPointerOver, this));

    [
      "pointerout",
      "focusout"
    ].forEach(e => this.addListener(e, this._onPointerOut, this));
  },

  statics: {
    ITEM_HEIGHT: 50,
    SHARED_USER: "@FontAwesome5Solid/user/16",
    SHARED_ORGS: "@FontAwesome5Solid/users/16",
    SHARED_ALL: "@FontAwesome5Solid/globe/16",
    STUDY_ICON: "@FontAwesome5Solid/file-alt/24",
    TEMPLATE_ICON: "@FontAwesome5Solid/copy/24",
    SERVICE_ICON: "@FontAwesome5Solid/paw/24",
    COMP_SERVICE_ICON: "@FontAwesome5Solid/cogs/24",
    DYNAMIC_SERVICE_ICON: "@FontAwesome5Solid/mouse-pointer/24",
    PERM_READ: "@FontAwesome5Solid/eye/16",
    POS: {
      THUMBNAIL: 0,
      TITLE: 1,
      DESCRIPTION: 2,
      SHARED: 3,
      LAST_CHANGE: 4,
      TSR: 5,
      TAGS: 6,
      OPTIONS: 7
    }
  },

  properties: {
    appearance: {
      refine : true,
      init : "pb-listitem"
    },

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

    uuid: {
      check: "String",
      apply: "_applyUuid"
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
      apply: "__applyFetching"
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new osparc.ui.basic.Thumbnail(null, 40, 35).set({
            minWidth: 40
          });
          control.getChildControl("image").set({
            anonymous: true
          });
          this._addAt(control, this.self().POS.THUMBNAIL);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label().set({
            font: "title-14",
            alignY: "middle"
          });
          this._addAt(control, this.self().POS.TITLE);
          break;
        case "description":
          control = new qx.ui.basic.Label().set({
            minWidth: 100,
            font: "text-14",
            alignY: "middle",
            allowGrowX: true
          });
          this._addAt(control, this.self().POS.DESCRIPTION, {
            flex: 1
          });
          break;
        case "shared-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._addAt(control, this.self().POS.SHARED);
          break;
        }
        case "last-change": {
          control = new qx.ui.basic.Label().set({
            anonymous: true,
            font: "text-13",
            allowGrowY: false,
            minWidth: 120,
            alignY: "middle"
          });
          this._addAt(control, this.self().POS.LAST_CHANGE);
          break;
        }
        case "tsr-rating": {
          const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2).set({
            alignY: "middle"
          })).set({
            toolTipText: this.tr("Ten Simple Rules"),
            minWidth: 50
          });
          const tsrLabel = new qx.ui.basic.Label(this.tr("TSR:"));
          tsrLayout.add(tsrLabel);
          control = new osparc.ui.basic.StarsRating();
          tsrLayout.add(control);
          this._addAt(tsrLayout, this.self().POS.TSR);
          break;
        }
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3)).set({
            anonymous: true,
            minWidth: 50
          });
          this._addAt(control, this.self().POS.TAGS);
          break;
        case "menu-button": {
          control = new qx.ui.form.MenuButton().set({
            width: 25,
            height: 25,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._addAt(control, this.self().POS.OPTIONS);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    isResourceType: function(resourceType) {
      return this.getResourceType() === resourceType;
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
          if (osparc.data.model.Node.isComputational(studyData)) {
            defaultThumbnail = this.self().COMP_SERVICE_ICON;
          }
          if (osparc.data.model.Node.isDynamic(studyData)) {
            defaultThumbnail = this.self().DYNAMIC_SERVICE_ICON;
          }
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
        quality: studyData.quality ? studyData.quality : null
      });
    },

    _applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);
    },

    _applyIcon: function(value, old) {
      const image = this.getChildControl("icon").getChildControl("image");
      image.set({
        source: value
      });
    },

    _applyTitle: function(value, old) {
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

    _applyDescription: function(value, old) {
      const label = this.getChildControl("description");
      label.setValue(value);
    },

    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("last-change");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    _applyAccessRights: function(value, old) {
      if (value && Object.keys(value).length) {
        const sharedIcon = this.getChildControl("shared-icon");

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
    },

    __applyFetching: function(value) {
      /*
      const title = this.getChildControl("title");
      if (value) {
        title.setValue(this.tr("Loading studies..."));
        this.setIcon("@FontAwesome5Solid/circle-notch/60");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        title.setValue(this.tr("Load More"));
        this.setIcon("@FontAwesome5Solid/paw/60");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .removeClass("rotate");
      }
      this.setEnabled(!value);
      */
    },

    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
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

    __filterText: function(text) {
      if (text) {
        const checks = [
          this.getTitle(),
          this.getDescription(),
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
    },

    _shouldReactToFilter: function(data) {
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

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
