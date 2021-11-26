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

qx.Class.define("osparc.dashboard.GridButtonItem", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function() {
    this.base(arguments);

    this.addListener("changeValue", this.__itemSelected, this);
  },

  events: {
    "updateQualityStudy": "qx.event.type.Data",
    "updateQualityTemplate": "qx.event.type.Data",
    "updateQualityService": "qx.event.type.Data"
  },

  statics: {
    MENU_BTN_WIDTH: 25
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tsr-mode-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
          this._mainLayout.addAt(control, osparc.dashboard.GridButtonBase.POS.TSR_MODE);
          break;
        case "tsr-rating": {
          const tsrModeLayout = this.getChildControl("tsr-mode-layout");
          const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
            toolTipText: this.tr("Ten Simple Rules")
          });
          const tsrLabel = new qx.ui.basic.Label(this.tr("TSR:"));
          tsrLayout.add(tsrLabel);
          control = new osparc.ui.basic.StarsRating();
          tsrLayout.add(control);
          tsrModeLayout.add(tsrLayout, {
            flex: 1
          });
          break;
        }
        case "ui-mode": {
          const tsrModeLayout = this.getChildControl("tsr-mode-layout");
          control = new qx.ui.basic.Image();
          tsrModeLayout.add(control);
          break;
        }
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3)).set({
            anonymous: true
          });
          this._mainLayout.addAt(control, osparc.dashboard.GridButtonBase.POS.TAGS);
          break;
        case "menu-button": {
          this.getChildControl("title").set({
            maxWidth: osparc.dashboard.GridButtonBase.ITEM_WIDTH - 2*osparc.dashboard.GridButtonBase.PADDING - this.self().MENU_BTN_WIDTH
          });
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
        }
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

    // overridden
    _applyMultiSelectionMode: function(value) {
      if (value) {
        const menuButton = this.getChildControl("menu-button");
        menuButton.setVisibility("excluded");
        this.__itemSelected();
      } else {
        this.__showMenuOnly();
      }
    },

    __itemSelected: function() {
      if (this.isResourceType("study") && this.isMultiSelectionMode()) {
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
    _applyLastChangeDate: function(value, old) {
      if (value && this.isResourceType("study")) {
        const label = this.getChildControl("subtitle-text");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    // overridden
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
          this._setStudyPermissions(value);
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
            image.setSource(osparc.dashboard.CardBase.SHARED_USER);
            break;
          case 1:
            image.setSource(osparc.dashboard.CardBase.SHARED_ORGS);
            break;
          case 2:
            image.setSource(osparc.dashboard.CardBase.SHARED_ALL);
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

    // overridden
    _applyMenu: function(value, old) {
      const menuButton = this.getChildControl("menu-button");
      if (value) {
        menuButton.setMenu(value);
      }
      menuButton.setVisibility(value ? "visible" : "excluded");
    }
  }
});
