/* gpu_cube — real 3D GPU workload for the Mali-400 via libhybris/fbdev EGL (no X needed).
 * Lit, depth-buffered, spinning cube with six colored faces + an FPS counter. Reuses the
 * proven EGL_DEFAULT_DISPLAY + NULL-window (fullscreen fbdev) path; our 8888->565 downconvert
 * in the fbdev platform handles the panel format. Usage: gpu_cube [frames]  (default 1800).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/time.h>
#include <signal.h>
#include <ucontext.h>
#include <unistd.h>
#include <fcntl.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

/* async-signal-safe crash reporter: dumps faulting PC/LR + /proc/self/maps so we can
 * map the addresses to a library+offset (and thus a function) on the host. */
static void _wr(const char *s){ write(2, s, strlen(s)); }
static void _whex(unsigned long v){
    char b[11]="0x00000000";
    for(int i=0;i<8;i++){ int nib=(v>>((7-i)*4))&0xf; b[2+i]=nib<10?('0'+nib):('a'+nib-10); }
    write(2,b,10);
}
static void _crash(int sig, siginfo_t *si, void *uc_){
    ucontext_t *uc=(ucontext_t*)uc_;
    _wr("\n*** CRASH sig="); _whex(sig);
    _wr(" pc="); _whex(uc->uc_mcontext.arm_pc);
    _wr(" lr="); _whex(uc->uc_mcontext.arm_lr);
    _wr(" fp="); _whex(uc->uc_mcontext.arm_fp);
    _wr(" addr="); _whex((unsigned long)si->si_addr);
    _wr("\n=== /proc/self/maps ===\n");
    int f=open("/proc/self/maps",O_RDONLY);
    if(f>=0){ char buf[8192]; int n; while((n=read(f,buf,sizeof buf))>0) write(2,buf,n); close(f); }
    _wr("=== end ===\n");
    _exit(139);
}
static void _install_crash(void){
    struct sigaction sa; memset(&sa,0,sizeof sa);
    sa.sa_sigaction=_crash; sa.sa_flags=SA_SIGINFO;
    sigaction(SIGSEGV,&sa,0); sigaction(SIGBUS,&sa,0); sigaction(SIGABRT,&sa,0);
}

static const char *VS =
"attribute vec3 aPos;\n"
"attribute vec3 aNormal;\n"
"attribute vec3 aColor;\n"
"uniform mat4 uMVP;\n"
"uniform mat4 uModel;\n"
"varying vec3 vN;\n"
"varying vec3 vColor;\n"
"void main(){\n"
"  gl_Position = uMVP * vec4(aPos,1.0);\n"
"  vN = normalize((uModel * vec4(aNormal,0.0)).xyz);\n"
"  vColor = aColor;\n"
"}\n";

static const char *FS =
"precision mediump float;\n"
"varying vec3 vN;\n"
"varying vec3 vColor;\n"
"void main(){\n"
"  vec3 L = normalize(vec3(0.4,0.7,1.0));\n"
"  float d = max(dot(normalize(vN), L), 0.0);\n"
"  float spec = pow(max(d,0.0), 16.0) * 0.4;\n"
"  vec3 c = vColor * (0.25 + 0.75*d) + vec3(spec);\n"
"  gl_FragColor = vec4(c, 1.0);\n"
"}\n";

/* ---- tiny column-major mat4 ---- */
static void m_identity(float *m){ memset(m,0,16*sizeof(float)); m[0]=m[5]=m[10]=m[15]=1.f; }
static void m_mul(float *r, const float *a, const float *b){
    float t[16];
    for(int c=0;c<4;c++) for(int row=0;row<4;row++){
        float s=0; for(int k=0;k<4;k++) s+=a[k*4+row]*b[c*4+k];
        t[c*4+row]=s;
    }
    memcpy(r,t,sizeof(t));
}
static void m_perspective(float *m, float fovy, float aspect, float n, float f){
    float tf = 1.f/tanf(fovy*0.5f);
    memset(m,0,16*sizeof(float));
    m[0]=tf/aspect; m[5]=tf; m[10]=(f+n)/(n-f); m[11]=-1.f; m[14]=(2.f*f*n)/(n-f);
}
static void m_translate(float *m, float x, float y, float z){
    m_identity(m); m[12]=x; m[13]=y; m[14]=z;
}
static void m_rotate(float *m, float a, float x, float y, float z){
    float c=cosf(a), s=sinf(a), l=sqrtf(x*x+y*y+z*z); x/=l;y/=l;z/=l;
    m_identity(m);
    m[0]=x*x*(1-c)+c;   m[1]=y*x*(1-c)+z*s; m[2]=x*z*(1-c)-y*s;
    m[4]=x*y*(1-c)-z*s; m[5]=y*y*(1-c)+c;   m[6]=y*z*(1-c)+x*s;
    m[8]=x*z*(1-c)+y*s; m[9]=y*z*(1-c)-x*s; m[10]=z*z*(1-c)+c;
}

static GLuint compile(GLenum type, const char *src){
    GLuint s=glCreateShader(type); glShaderSource(s,1,&src,0); glCompileShader(s);
    GLint ok=0; glGetShaderiv(s,GL_COMPILE_STATUS,&ok);
    if(!ok){ char log[512]; glGetShaderInfoLog(s,512,0,log); fprintf(stderr,"shader: %s\n",log); }
    return s;
}

int main(int argc, char **argv){
    int frames = (argc==2)? atoi(argv[1]) : 1800;
    if(!getenv("NOCRASH")) _install_crash();

    EGLDisplay dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    eglInitialize(dpy,0,0);
    EGLint cfg_attr[] = {
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_DEPTH_SIZE, 16,
        EGL_NONE
    };
    EGLConfig cfg; EGLint ncfg=0;
    eglChooseConfig(dpy, cfg_attr, &cfg, 1, &ncfg);
    fprintf(stderr,"gpu_cube: configs matched=%d\n", ncfg);
    EGLint ctx_attr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctx_attr);
    EGLSurface surf = eglCreateWindowSurface(dpy, cfg, (EGLNativeWindowType)NULL, NULL);
    if(surf==EGL_NO_SURFACE){ fprintf(stderr,"no surface 0x%x\n", eglGetError()); return 1; }
    eglMakeCurrent(dpy, surf, surf, ctx);

    EGLint W=0,H=0; eglQuerySurface(dpy,surf,EGL_WIDTH,&W); eglQuerySurface(dpy,surf,EGL_HEIGHT,&H);
    if(W<=0)W=800; if(H<=0)H=1280;
    fprintf(stderr,"gpu_cube: surface %dx%d, GL_RENDERER=%s\n", W,H, (const char*)glGetString(GL_RENDERER));

    GLuint prog=glCreateProgram();
    glAttachShader(prog, compile(GL_VERTEX_SHADER,VS));
    glAttachShader(prog, compile(GL_FRAGMENT_SHADER,FS));
    glLinkProgram(prog); glUseProgram(prog);
    GLint aPos=glGetAttribLocation(prog,"aPos");
    GLint aNormal=glGetAttribLocation(prog,"aNormal");
    GLint aColor=glGetAttribLocation(prog,"aColor");
    GLint uMVP=glGetUniformLocation(prog,"uMVP");
    GLint uModel=glGetUniformLocation(prog,"uModel");

    /* build cube: 6 faces * 2 tris * 3 verts, each pos(3)+normal(3)+color(3) */
    float cn[8][3]={{-1,-1,-1},{1,-1,-1},{1,1,-1},{-1,1,-1},{-1,-1,1},{1,-1,1},{1,1,1},{-1,1,1}};
    int fq[6][4]={{4,5,6,7},{1,0,3,2},{5,1,2,6},{0,4,7,3},{7,6,2,3},{0,1,5,4}};
    float fn[6][3]={{0,0,1},{0,0,-1},{1,0,0},{-1,0,0},{0,1,0},{0,-1,0}};
    float fc[6][3]={{1,.2,.2},{.2,1,.2},{.2,.2,1},{1,1,.2},{1,.2,1},{.2,1,1}};
    float V[36*9]; int vi=0;
    int tri[6]={0,1,2,0,2,3};
    for(int f=0;f<6;f++) for(int t=0;t<6;t++){
        int ci=fq[f][tri[t]];
        V[vi++]=cn[ci][0]; V[vi++]=cn[ci][1]; V[vi++]=cn[ci][2];
        V[vi++]=fn[f][0];  V[vi++]=fn[f][1];  V[vi++]=fn[f][2];
        V[vi++]=fc[f][0];  V[vi++]=fc[f][1];  V[vi++]=fc[f][2];
    }

    glEnable(GL_DEPTH_TEST);
    glViewport(0,0,W,H);
    glClearColor(0.05f,0.05f,0.08f,1.f);

    float proj[16]; m_perspective(proj, 1.0f, (float)W/(float)H, 1.f, 100.f);
    float view[16]; m_translate(view, 0,0,-6.f);

    struct timeval t0,tp; gettimeofday(&t0,0); tp=t0;
    float ang=0.f;
    for(int i=0;i<frames;i++){
        ang += 0.02f;
        float rY[16],rX[16],model[16],vp[16],mvp[16];
        m_rotate(rY, ang, 0,1,0);
        m_rotate(rX, ang*0.7f, 1,0,0);
        m_mul(model, rY, rX);
        m_mul(vp, proj, view);
        m_mul(mvp, vp, model);
        glUniformMatrix4fv(uMVP,1,GL_FALSE,mvp);
        glUniformMatrix4fv(uModel,1,GL_FALSE,model);

        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
        glVertexAttribPointer(aPos,3,GL_FLOAT,GL_FALSE,9*sizeof(float),V);
        glEnableVertexAttribArray(aPos);
        glVertexAttribPointer(aNormal,3,GL_FLOAT,GL_FALSE,9*sizeof(float),V+3);
        glEnableVertexAttribArray(aNormal);
        glVertexAttribPointer(aColor,3,GL_FLOAT,GL_FALSE,9*sizeof(float),V+6);
        glEnableVertexAttribArray(aColor);
        glDrawArrays(GL_TRIANGLES,0,36);
        eglSwapBuffers(dpy,surf);

        if((i+1)%60==0){
            struct timeval now; gettimeofday(&now,0);
            double dt=(now.tv_sec-tp.tv_sec)+(now.tv_usec-tp.tv_usec)/1e6;
            printf("frame %d  |  %.1f fps\n", i+1, 60.0/dt); fflush(stdout);
            tp=now;
        }
    }
    struct timeval te; gettimeofday(&te,0);
    double total=(te.tv_sec-t0.tv_sec)+(te.tv_usec-t0.tv_usec)/1e6;
    printf("=== %d frames in %.2fs = %.1f fps average ===\n", frames, total, frames/total);
    return 0;
}
