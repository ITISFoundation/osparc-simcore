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


qx.Class.define("osparc.component.widget.StudyCardLarge", {
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

    this.__studyData = studyData;

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

    __createTitle: function() {
      const title = new qx.ui.basic.Label(this.__studyData["name"]).set({
        font: "title-16",
        allowStretchX: true
      });
      return title;
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

    __createUuid: function() {
      const uuid = new qx.ui.basic.Label(this.__studyData["uuid"]).set({
        maxWidth: 120,
        tooltTipText: this.__studyData["uuid"]
      });
      return uuid;
    },

    __createOwner: function() {
      const owner = new qx.ui.basic.Label().set({
        value: osparc.utils.Utils.getNameFromEmail(this.__studyData["prjOwner"]),
        toolTipText: this.__studyData["prjOwner"]
      });
      return owner;
    },

    __createCreationDate: function() {
      const date = osparc.utils.Utils.formatDateAndTime(new Date(this.__studyData["creationDate"]));
      const creationDate = new qx.ui.basic.Label(date);
      return creationDate;
    },

    __createLastChangeDate: function() {
      const date = osparc.utils.Utils.formatDateAndTime(new Date(this.__studyData["lastChangeDate"]));
      const lastChangeDate = new qx.ui.basic.Label(date);
      return lastChangeDate;
    },

    __createAccessRights: function() {
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = this.__studyData["accessRights"];
      if (myGID in ar) {
        if (ar[myGID]["delete"]) {
          permissions = this.tr("Owner");
        } else if (ar[myGID]["write"]) {
          permissions = this.tr("Collaborator");
        } else if (ar[myGID]["read"]) {
          permissions = this.tr("Viewer");
        }
      }
      const accessRights = new qx.ui.basic.Label(permissions);
      return accessRights;
    },

    __createQuality: function() {
      const quality = this.__studyData["quality"];
      if (quality && "tsr" in quality) {
        const tsrLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(2)).set({
          toolTipText: this.tr("Ten Simple Rules score")
        });
        const {
          score,
          maxScore
        } = osparc.component.metadata.Quality.computeTSRScore(quality["tsr"]);
        const tsrRating = new osparc.ui.basic.StarsRating();
        tsrRating.set({
          score,
          maxScore,
          nStars: 4,
          showScore: true
        });
        tsrLayout.add(tsrRating);

        return tsrLayout;
      }
      return null;
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 160;
      const image = new osparc.component.widget.Thumbnail(null, maxWidth, maxHeight);
      const img = image.getChildControl("image");
      img.set({
        source: this.__studyData["thumbnail"],
        visibility: this.__studyData["thumbnail"] ? "visible" : "excluded"
      });
      return image;
    },

    __createDescription: function() {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: false,
        maxHeight: 300,
        value: this.__studyData["description"]
      });
      return description;
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
