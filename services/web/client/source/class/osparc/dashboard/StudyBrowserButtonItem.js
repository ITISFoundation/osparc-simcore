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

    // create a date format like "Oct. 19, 2018 11:31 AM"
    this.__dateFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getDateFormat("medium")
    );
    this.__timeFormat = new qx.util.format.DateFormat(
      qx.locale.Date.getTimeFormat("short")
    );

    this.addListener("changeValue", this.__itemSelected, this);
  },

  properties: {
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
      apply: "_applyStudyDescription",
      nullable: true
    },

    creator: {
      check: "String",
      apply: "_applyCreator",
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

    tags: {
      check: "Array",
      apply: "_applyTags"
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

    lockedBy: {
      check: "String",
      nullable: true,
      apply: "_applyLockedBy"
    }
  },

  statics: {
    MENU_BTN_WIDTH: 25,
    SHARED_USER: "@FontAwesome5Solid/user/14",
    SHARED_ORGS: "@FontAwesome5Solid/users/14",
    SHARED_ALL: "@FontAwesome5Solid/globe/14"
  },

  members: {
    __dateFormat: null,
    __timeFormat: null,

    isResourceType: function(resourceType) {
      return this.getResourceType() === resourceType;
    },

    multiSelection: function(on) {
      if (on) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("excluded");
        this.__itemSelected();
      } else {
        this.__showMenuOnly();
      }
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
        case "lock":
          control = new osparc.component.widget.Thumbnail("@FontAwesome5Solid/lock/70");
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
      }

      return control || this.base(arguments, id);
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

    _applyStudyDescription: function(value, old) {
      /*
      if (value !== "" && this.isResourceType("template")) {
        const label = this.getChildControl("description");
        label.setValue(value);
      }
      */
    },

    _applyLastChangeDate: function(value, old) {
      if (value && this.isResourceType("study")) {
        const label = this.getChildControl("description2");
        let dateStr = null;
        if (value.getDate() === (new Date()).getDate()) {
          dateStr = this.tr("Today");
        } else if (value.getDate() === (new Date()).getDate() - 1) {
          dateStr = this.tr("Yesterday");
        } else {
          dateStr = this.__dateFormat.format(value);
        }
        const timeStr = this.__timeFormat.format(value);
        label.setValue(dateStr + " " + timeStr);
      }
    },

    _applyCreator: function(value, old) {
      if (this.isResourceType("service") || this.isResourceType("template")) {
        const label = this.getChildControl("description2");
        label.setValue(value);
      }
    },

    _applyAccessRights: function(value, old) {
      if (value && Object.keys(value).length) {
        const image = this.getChildControl("shared");

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
            this.__setSharedIcon(image, value, groups);
          });
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
          const tagUI = new osparc.ui.basic.Tag(tag.name, tag.color, "studyBrowser");
          tagUI.setFont("text-12");
          tagsContainer.add(tagUI);
        });
      }
    },

    _applyState: function(state) {
      const locked = ("locked" in state) ? state["locked"]["value"] : false;
      if (locked) {
        this.setLocked(state["locked"]["value"]);
        const owner = state["locked"]["owner"];
        this.setLockedBy(osparc.utils.Utils.firstsUp(owner["first_name"], owner["last_name"]));
      } else {
        this.setLocked(false);
        this.setLockedBy(null);
      }
    },

    _applyLocked: function(locked) {
      this.set({
        cursor: locked ? "not-allowed" : "pointer"
      });

      this._getChildren().forEach(item => {
        item.setOpacity(locked ? 0.4 : 1.0);
      });

      const lock = this.getChildControl("lock");
      lock.setOpacity(1.0);
      lock.setVisibility(locked ? "visible" : "excluded");

      [
        "tick-selected",
        "tick-unselected",
        "menu-button"
      ].forEach(childName => {
        const child = this.getChildControl(childName);
        child.set({
          enabled: !locked
        });
      });
    },

    _applyLockedBy: function(lockedBy) {
      this.set({
        toolTipText: lockedBy ? (lockedBy + this.tr(" is using it")) : null
      });
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const checks = [
          this.getStudyTitle(),
          this.getCreator()
        ];
        if (checks.filter(label => label.toLowerCase().trim().includes(data.text)).length == 0) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const tagNames = this.getTags().map(tag => tag.name);
        if (data.tags.filter(tag => tagNames.includes(tag)).length == 0) {
          return true;
        }
      }
      return false;
    }
  },

  destruct : function() {
    this.__dateFormat.dispose();
    this.__dateFormat = null;
    this.__timeFormat.dispose();
    this.__timeFormat = null;
  }
});
