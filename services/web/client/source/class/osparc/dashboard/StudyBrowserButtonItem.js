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

    this.addListener("changeValue", e => {
      const val = this.getValue();

      const tick = this.getChildControl("tick-selected");
      tick.setVisibility(val ? "visible" : "excluded");

      const untick = this.getChildControl("tick-unselected");
      untick.setVisibility(val ? "excluded" : "visible");
    });
  },

  properties: {
    isTemplate: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsTemplate"
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
    }
  },

  statics: {
    MENU_BTN_Z: 20,
    MENU_BTN_WIDTH: 25,
    SHARED_USER: "@FontAwesome5Solid/user/14",
    SHARED_ORGS: "@FontAwesome5Solid/users/14",
    SHARED_ALL: "@FontAwesome5Solid/globe/14"
  },

  members: {
    __dateFormat: null,
    __timeFormat: null,

    multiSelection: function(on) {
      const menuButton = this.getChildControl("menu-button");
      menuButton.setVisibility(on ? "excluded" : "visible");
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
            zIndex: this.self().MENU_BTN_Z,
            focusable: false
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._add(control, {
            top: -2,
            right: -2
          });
          break;
        case "tick-unselected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/circle/16").set({
            zIndex: this.self().MENU_BTN_Z -1
          });
          this._add(control, {
            top: 4,
            right: 4
          });
          break;
        case "tick-selected":
          control = new qx.ui.basic.Image("@FontAwesome5Solid/check-circle/16").set({
            zIndex: this.self().MENU_BTN_Z -1
          });
          this._add(control, {
            top: 4,
            right: 4
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
      if (value !== "" && this.getIsTemplate()) {
        const label = this.getChildControl("description");
        label.setValue(value);
      }
      */
    },

    _applyLastChangeDate: function(value, old) {
      if (value && !this.getIsTemplate()) {
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
      if (this.getIsTemplate()) {
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
          store.getGroupsMe(),
          store.getVisibleMembers(),
          store.getGroupsOrganizations()
        ])
          .then(values => {
            const all = values[0];
            const me = values[1];
            const orgMembs = [];
            const orgMembers = values[2];
            for (const gid of Object.keys(orgMembers)) {
              orgMembs.push(orgMembers[gid]);
            }
            const orgs = values.length === 4 ? values[3] : [];
            const groups = [[all], orgs, orgMembs, [me]];
            this.__setSharedIcon(image, value, groups);
          });
      }
    },

    __setSharedIcon: function(image, value, groups) {
      const myGroupId = osparc.auth.Data.getInstance().getGroupId();
      for (let i=0; i<groups.length; i++) {
        const sharedGrps = [];
        const gids = Object.keys(value);
        for (let j=0; j<gids.length; j++) {
          const gid = parseInt(gids[j]);
          if (!this.getIsTemplate() && (gid === myGroupId)) {
            continue;
          }
          const grp = groups[i].find(group => group["gid"] === gid);
          if (grp) {
            sharedGrps.push(grp);
          }
        }
        if (sharedGrps.length === 0) {
          continue;
        }
        switch (i) {
          case 0:
            image.setSource(this.self().SHARED_ALL);
            break;
          case 1:
            image.setSource(this.self().SHARED_ORGS);
            break;
          case 2:
          case 3:
            image.setSource(this.self().SHARED_USER);
            break;
        }

        let hintText = "";
        sharedGrps.forEach(sharedGrp => {
          hintText += (sharedGrp["label"] + "<br>");
        });
        const hint = new osparc.ui.hint.Hint(image, hintText).set({
          active: false
        });
        image.addListener("mouseover", () => hint.show(), this);
        image.addListener("mouseout", () => hint.exclude(), this);

        break;
      }
      if (image.getSource() === null) {
        image.setVisibility("excluded");
      }
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
