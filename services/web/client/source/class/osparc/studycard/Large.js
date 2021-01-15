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


qx.Class.define("osparc.studycard.Large", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} Serialized Study Object
    */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(5));

    if (studyData && studyData instanceof Object) {
      this.__studyData = studyData;
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 230,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 200
  },

  members: {
    __studyData: null,

    checkResize: function(bounds) {
      this.__rebuildLayout(bounds.width);
    },

    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __isOwner: function() {
      return osparc.data.model.Study.isOwner(this.__studyData);
    },

    __rebuildLayout: function(width) {
      this._removeAll();

      const nameAndMenuButton = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignY: "middle"
      }));
      nameAndMenuButton.add(this.__createTitle(), {
        flex: 1
      });
      if (this.__isOwner()) {
        const editTitleBtn = osparc.utils.Utils.getEditButton();
        editTitleBtn.addListener("execute", () => {
          this.__openTitleEditor();
        }, this);
        nameAndMenuButton.add(editTitleBtn);
      }
      this._add(nameAndMenuButton);

      const extraInfo = this.__extraInfo();

      const bounds = this.getBounds();
      let widgetWidth = null;
      if (width) {
        widgetWidth = width;
      } else if (bounds) {
        widgetWidth = bounds.width;
      } else {
        widgetWidth = 500;
      }
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING;
      if (slim) {
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        this._add(extraInfo);
        this._add(thumbnail);
      } else {
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center",
          alignY: "middle"
        }));
        hBox.add(extraInfo);
        hBox.add(thumbnail, {
          flex: 1
        });
        this._add(hBox);
      }

      this._add(this.__createDescription());
    },

    __extraInfo: function() {
      const grid = new qx.ui.layout.Grid(6, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid).set({
        width: this.self().EXTRA_INFO_WIDTH,
        alignX: "center",
        alignY: "middle"
      });

      const extraInfo = [
        [this.tr("uuid"), this.__createUuid(), null],
        [this.tr("Author"), this.__createOwner(), null],
        [this.tr("Creation date"), this.__createCreationDate(), null],
        [this.tr("Last modified"), this.__createLastChangeDate(), null],
        [this.tr("Access rights"), this.__createAccessRights(), this.__openAccessRightsEditor],
        [this.tr("Quality"), this.__createQuality(), this.__openQualityEditor]
      ];
      for (let i=0; i<extraInfo.length; i++) {
        if (extraInfo[i][1]) {
          moreInfo.add(new qx.ui.basic.Label(extraInfo[i][0]).set({
            font: "title-12"
          }), {
            row: i,
            column: 0
          });

          moreInfo.add(extraInfo[i][1], {
            row: i,
            column: 1
          });

          if (extraInfo[i][2] && this.__isOwner()) {
            const editTitleBtn = osparc.utils.Utils.getEditButton();
            editTitleBtn.addListener("execute", () => {
              extraInfo[i][2].call(this);
            }, this);
            moreInfo.add(editTitleBtn, {
              row: i,
              column: 2
            });
          }
        }
      }

      return moreInfo;
    },

    __createTitle: function() {
      const title = osparc.studycard.Utils.createTitle(this.__studyData).set({
        font: "title-16"
      });
      return title;
    },

    __createUuid: function() {
      return osparc.studycard.Utils.createUuid(this.__studyData);
    },

    __createOwner: function() {
      return osparc.studycard.Utils.createOwner(this.__studyData);
    },

    __createCreationDate: function() {
      return osparc.studycard.Utils.createCreationDate(this.__studyData);
    },

    __createLastChangeDate: function() {
      return osparc.studycard.Utils.createLastChangeDate(this.__studyData);
    },

    __createAccessRights: function() {
      return osparc.studycard.Utils.createAccessRights(this.__studyData);
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.__studyData);
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 160;
      return osparc.studycard.Utils.createThumbnail(this.__studyData, maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.studycard.Utils.createDescription(this.__studyData, maxHeight);
    },

    __openTitleEditor: function() {

    },

    __openAccessRightsEditor: function() {
      const permissionsView = new osparc.component.export.StudyPermissions(this.__studyData);
      const title = this.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateStudy", e => {
        const studyId = e.getData();
        this._reloadStudy(studyId);
      }, this);
    },

    __openQualityEditor: function() {
      const qualityEditor = new osparc.component.metadata.QualityEditor(this.__studyData);
      const title = this.__studyData["name"] + " - " + this.tr("Quality Assessment");
      osparc.ui.window.Window.popUpInWindow(qualityEditor, title, 650, 760);
      qualityEditor.addListener("updateStudy", e => {
        const updatedStudyData = e.getData();
        this._resetStudyItem(updatedStudyData);
      });
      qualityEditor.addListener("updateTemplate", e => {
        const updatedTemplateData = e.getData();
        this._resetTemplateItem(updatedTemplateData);
      });
      qualityEditor.addListener("updateService", e => {
        const updatedServiceData = e.getData();
        this._resetServiceItem(updatedServiceData);
      });
    },

    __openThumbnailEditor: function() {

    },

    __openDescriptionEditor: function() {

    }
  }
});
