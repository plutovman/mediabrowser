
#=========================================
#					  
#              local.env
#
# This script sets up the environment for
#	tav
#	maya
#  	houdini
#
# Last modified on 05/25/05			
#=========================================


# ==== JOB ENVIRONMET VARIABLES ============
setenv JOB_YEAR generic
setenv JOB_NAME generic
setenv JOBS_DIR /replace/with/dir
setenv IMAGE_NAME generic
setenv JOB_DIR /replace/with/dir
setenv VDROP /replace/with/dir
setenv JOB_ARCH_SEQ /replace/with/dir
setenv JOB_ARCH_VID /replace/with/dir

# ==== SETTING USER ENVIRONMENT===================
source ~/.login
# ==== SETTING MAYA ENVIRONMENT=============
setenv MAYA_DIR $JOB_DIR/maya
setenv WF_IMG_DIR /replace/with/dir
setenv WF_OBJ_DIR  $MAYA_DIR/obj

setenv MAYA_PROJECT /default
set path_maya_scripts = /default
setenv MAYA_SCRIPT_PATH "$path_maya_scripts"
# ==== SCENE CONTROL =======================
echo ""
echo "...local env now set to:" $JOB_DIR
echo ""

# ==== ALIASES ===============================

alias job	'cd $JOB_DIR'
alias jobs	'cd $JOBS_DIR'
alias anim	'cd $JOB_DIR/maya/anim'
alias depth	'cd $JOB_DIR/maya/depth'
alias dxf       'cd $JOB_DIR/maya/dxf'
alias explore	'cd $JOB_DIR/maya/explore'
alias fura	'cd $JOB_DIR/maya/furAttrMap'
alias fure	'cd $JOB_DIR/maya/furEqualMap'
alias furf	'cd $JOB_DIR/maya/furFiles'
alias furi	'cd $JOB_DIR/maya/furImages'
alias furs	'cd $JOB_DIR/maya/furShadowMap'
alias iges      'cd $JOB_DIR/maya/iges'
alias img 	'cd $IMAGE_NAME'
alias ipr	'cd $JOB_DIR/maya/iprImages'
alias lights    'cd $JOB_DIR/maya/lights'
alias mel	'cd $JOB_DIR/maya/mel'
alias move	'cd $JOB_DIR/maya/move'
alias mayaren   'cd $JOB_DIR/maya/render'
alias rnd	'cd $JOB_DIR/maya/render'
alias rib       'cd $JOB_DIR/maya/rib'
alias scenes    'cd $JOB_DIR/maya/scenes'
alias scn       'cd $JOB_DIR/maya/scenes'
alias sound	'cd $JOB_DIR/maya/sound'
alias soimg     'cd $JOB_DIR/maya/sourceimages'
alias textures  'cd $JOB_DIR/maya/textures'
alias mtex	'cd $JOB_DIR/maya/textures'
alias vrml	'cd $JOB_DIR/maya/vrml2'
alias wire	'cd $JOB_DIR/maya/aliasWireExport'
alias o     	'cd $WF_OBJ_DIR'

alias hou	'cd $JOB_DIR/houdini'
alias mya	'cd $JOB_DIR/maya'

alias bgeo       'cd $JOB_DIR/houdini/bgeo'
alias hip       'cd $JOB_DIR/houdini/hip'
alias htex       'cd $JOB_DIR/houdini/tex'
alias otl       'cd $JOB_DIR/houdini/otl'
alias hscripts   'cd $JOB_DIR/houdini/scripts'

alias afx	'cd $JOB_DIR/afterfx'
alias data	'cd $JOB_DIR/data'
alias prm	'cd $JOB_DIR/premiere'
alias py	'cd $JOB_DIR/python'
alias psd	'cd $JOB_DIR/photoshop'
alias shk	'cd $JOB_DIR/shake'
alias nk	'cd $JOB_DIR/nuke'
alias zbr	'cd $JOB_DIR/zbrush'
alias vu	'cd $JOB_DIR/vue'

alias drop	'cd $VDROP'
alias iseq	'cd $VDROP/imgseq'
alias iraw	'cd $VDROP/imgseq/raw'
alias ifin	'cd $VDROP/imgseq/fin'
alias arcs	'cd $JOB_ARCH_SEQ'
alias arcv	'cd $JOB_ARCH_VID'
