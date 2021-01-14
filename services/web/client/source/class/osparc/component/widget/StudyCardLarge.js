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
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(3));

    if (study) {
      if (study instanceof osparc.data.model.Study) {
        this.setStudy(study);
      } else {
        this.setStudyData(study);
      }
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      apply: "__applyStudy",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 250,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 250
  },

  members: {
    /**
      * @param studyData {Object} Serialized Study Object
      */
    setStudyData: function(studyData) {
      const study = new osparc.data.model.Study(studyData, false);
      this.setStudy(study);
    },

    checkResize: function(bounds) {
      this.__rebuildLayout(bounds.width);
    },

    __applyStudy: function() {
      this.__rebuildLayout();
    },

    __isOwner: function() {
      return osparc.data.model.Study.isOwner(this.getStudy());
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
        widgetWidth = 350;
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
      const title = new qx.ui.basic.Label().set({
        font: "title-16",
        allowStretchX: true,
        rich: true
      });
      this.getStudy().bind("name", title, "value");
      return title;
    },

    __extraInfo: function() {
      const grid = new qx.ui.layout.Grid(5, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      grid.setColumnFlex(2, 0);
      const moreInfo = new qx.ui.container.Composite(grid).set({
        width: this.self().EXTRA_INFO_WIDTH,
        alignX: "center",
        alignY: "middle"
      });

      const extraInfo = [
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

    __createOwner: function() {
      const owner = new qx.ui.basic.Label();
      this.getStudy().bind("prjOwner", owner, "value", {
        converter: email => osparc.utils.Utils.getNameFromEmail(email),
        onUpdate: (source, target) => {
          target.setToolTipText(source.getPrjOwner());
        }
      });
      return owner;
    },

    __createCreationDate: function() {
      const dateOptions = {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      };
      const creationDate = new qx.ui.basic.Label();
      this.getStudy().bind("creationDate", creationDate, "value", dateOptions);
      return creationDate;
    },

    __createLastChangeDate: function() {
      const dateOptions = {
        converter: date => osparc.utils.Utils.formatDateAndTime(date)
      };
      const lastChangeDate = new qx.ui.basic.Label();
      this.getStudy().bind("lastChangeDate", lastChangeDate, "value", dateOptions);
      return lastChangeDate;
    },

    __createAccessRights: function() {
      let permissions = "";
      const myGID = osparc.auth.Data.getInstance().getGroupId();
      const ar = this.getStudy().getAccessRights();
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
      const quality = this.getStudy().getQuality();
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

        this.getStudy().addListener("changeQuality", e => {
          console.log("changeQuality", e.getData());
        });

        return tsrLayout;
      }
      return null;
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 150;
      const image = new osparc.component.widget.Thumbnail(null, maxWidth, maxHeight);
      const img = image.getChildControl("image");
      this.getStudy().bind("thumbnail", img, "source");
      this.getStudy().bind("thumbnail", img, "visibility", {
        converter: thumbnail => {
          if (thumbnail) {
            return "visible";
          }
          return "excluded";
        }
      });
      return image;
    },

    __createDescription: function() {
      const description = new osparc.ui.markdown.Markdown().set({
        noMargin: false,
        maxHeight: 300
      });
      this.getStudy().bind("description", description, "value");
      return description;
    },

    __openTitleEditor: function() {

    },

    __openAccessRightsEditor: function() {
      const studyData = this.getStudy().serialize();
      const permissionsView = new osparc.component.export.StudyPermissions(studyData);
      const title = this.tr("Share with Collaborators and Organizations");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateStudy", e => {
        const studyId = e.getData();
        this._reloadStudy(studyId);
      }, this);
    },

    __openQualityEditor: function() {
      const studyData = this.getStudy().serialize();
      const qualityEditor = new osparc.component.metadata.QualityEditor(studyData);
      const title = this.getStudy().getName() + " - " + this.tr("Quality Assessment");
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
