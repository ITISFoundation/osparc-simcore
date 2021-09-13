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
    PERM_READ: "@FontAwesome5Solid/eye/14"
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
      apply: "_applyFetching"
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

    __applyUuid: function(value, old) {
      osparc.utils.Utils.setIdToWidget(this, "studyBrowserListItem_"+value);
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

    _applyQuality: function(quality) {
      throw new Error("Abstract method called!");
    },

    _applyState: function(state) {
      throw new Error("Abstract method called!");
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
