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


qx.Class.define("osparc.info.StudyMedium", {
  extend: qx.ui.core.Widget,

  /**
    * @param study {osparc.data.model.Study} Study
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: 0,
      backgroundColor: "background-main"
    });
    this._setLayout(new qx.ui.layout.VBox(20));

    if (study) {
      this.setStudy(study);
    }

    this.addListenerOnce("appear", () => this.__rebuildLayout(), this);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  members: {
    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __rebuildLayout: function() {
      this._removeAll();

      const nameAndMenuButton = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      nameAndMenuButton.add(this.__createMenuButton());
      nameAndMenuButton.add(osparc.info.StudyUtils.createTitle(this.getStudy()), {
        flex: 1
      });
      this._add(nameAndMenuButton);

      const thumbnail = this.__createThumbnail(160, 100);
      if (thumbnail) {
        this._add(thumbnail);
      }

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);
      this._add(extraInfoLayout);

      const description = osparc.info.StudyUtils.createDescription(this.getStudy());
      this._add(description);
    },

    __createMenuButton: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const menuButton = new qx.ui.form.MenuButton().set({
        menu,
        width: 25,
        height: 25,
        icon: "@FontAwesome5Solid/ellipsis-v/14",
        focusable: false,
        allowGrowY: false
      });

      const infoButton = new qx.ui.menu.Button(this.tr("Information..."));
      infoButton.addListener("execute", () => this.__openStudyDetails(), this);
      menu.add(infoButton);

      const shareButton = new qx.ui.menu.Button(this.tr("Share..."));
      shareButton.addListener("execute", () => this.__openAccessRights(), this);
      menu.add(shareButton);

      return menuButton;
    },

    __extraInfo: function() {
      const extraInfo = [{
        label: this.tr("AUTHOR"),
        view: osparc.info.StudyUtils.createOwner(this.getStudy())
      }, {
        label: this.tr("ACCESS RIGHTS"),
        view: osparc.info.StudyUtils.createAccessRights(this.getStudy())
      }, {
        label: this.tr("SHARED"),
        view: osparc.info.StudyUtils.createShared(this.getStudy())
      }, {
        label: this.tr("CREATED"),
        view: osparc.info.StudyUtils.createCreationDate(this.getStudy())
      }, {
        label: this.tr("MODIFIED"),
        view: osparc.info.StudyUtils.createLastChangeDate(this.getStudy())
      }];

      if (
        osparc.product.Utils.showQuality() &&
        osparc.metadata.Quality.isEnabled(this.getStudy().getQuality())
      ) {
        extraInfo.push({
          label: this.tr("QUALITY"),
          view: osparc.info.StudyUtils.createQuality(this.getStudy())
        });
      }

      const tagsContainer = osparc.info.StudyUtils.createTags(this.getStudy()).set({
        maxWidth: 150,
      });
      extraInfo.push({
        label: this.tr("TAGS"),
        view: tagsContainer
      });

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.Utils.extraInfosToGrid(extraInfo);
      return moreInfo;
    },

    __createThumbnail: function(maxWidth, maxHeight = 150) {
      if (this.getStudy().getThumbnail()) {
        return osparc.info.StudyUtils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
      }
      return null;
    },

    __openStudyDetails: function() {
      const studyDetails = new osparc.info.StudyLarge(this.getStudy());
      const title = this.tr("Project Information");
      const width = osparc.info.CardLarge.WIDTH;
      const height = osparc.info.CardLarge.HEIGHT;
      osparc.ui.window.Window.popUpInWindow(studyDetails, title, width, height).set({
        maxHeight: height
      });
    },

    __openAccessRights: function() {
      const studyData = this.getStudy().serialize();
      studyData["resourceType"] = this.getStudy().getTemplateType() ? "template" : "study";
      const collaboratorsView = osparc.info.StudyUtils.openAccessRights(studyData);
      collaboratorsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },
  }
});
