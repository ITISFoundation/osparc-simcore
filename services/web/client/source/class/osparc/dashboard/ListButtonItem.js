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
  extend: osparc.dashboard.ListButtonBase,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "shared-icon": {
          control = new qx.ui.basic.Image().set({
            minWidth: 50,
            alignY: "middle"
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.SHARED);
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
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.LAST_CHANGE);
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
          this._addAt(tsrLayout, osparc.dashboard.ListButtonBase.POS.TSR);
          break;
        }
        case "tags":
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(5, 3)).set({
            anonymous: true,
            minWidth: 50
          });
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.TAGS);
          break;
        case "menu-button": {
          control = new qx.ui.form.MenuButton().set({
            width: 25,
            height: 25,
            icon: "@FontAwesome5Solid/ellipsis-v/14",
            focusable: false
          });
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
          this._addAt(control, osparc.dashboard.ListButtonBase.POS.OPTIONS);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("last-change");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    },

    // overridden
    _applyOwner: function(value, old) {
      return;
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

    _applyState: function(state) {
    },

    _applyFetching: function(value) {
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
    }
  },

  destruct : function() {
    this.removeListener("pointerover", this._onPointerOver, this);
    this.removeListener("pointerout", this._onPointerOut, this);
  }
});
