import os, sys
import git
import paramiko
import glob
import Log
import json
import yaml
import time


# self.log.basicConfig(level=self.log.DEBUG,format='%(asctime)s %(filename)s[line:%(lineno)d] %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
class SyncCode():
    isRuning = False
    # 工作目录
    basePath = "/app"
    # 项目地址
    projectPath = "sources"
    configs = []
    # 最后一次提交
    lastcommit = ''
    isError = False
    errorConfigs = {}
    log = Log.Logger('logs/build.log', level='debug').logger

    def __init__(self):
        self.loadConfig(self.basePath)

    def loadConfig(self, basePath):
        self.configs.clear()
        self.log.info("切换工作目录:%s" % self.basePath)
        # 工作目录
        os.chdir(basePath)
        # 配置文件
        configFiles = glob.glob(r'**.package')
        for filePath in configFiles:
            self.log.info("查找到配置文件:%s" % filePath)
            # 初始化配置文件
            tempfile = open(filePath, 'r', encoding="utf-8")
            config = yaml.safe_load(tempfile)
            self.log.info(config)
        self.configs.append(config)

    def autoSync(self):
        env_dist = os.environ
        interval = env_dist.get('git.interval', 60)
        self.log.info("开始执行自动同步,检查间隔时间为:%s秒" % interval)
        while (True):
            for config in self.configs:
                if (self.gitClone(config)):
                    self.log.info("监测到代码变动")
                    self.sync(config)
                if (self.isError):
                    self.log.info("上一次执行错误,休息10秒后继续执行")
                    time.sleep(10)
                    for configName in self.errorConfigs:
                        try:
                            self.log.info("开始执行错误的配置%s" % configName)
                            self.syncOne(config,configName)
                        except:
                            continue
            time.sleep(interval)
            self.log.info("休眠后重新刷新配置")
            self.loadConfig(self.basePath)
            self.log.info("刷新配置完成")

    def gitClone(self, config):
        change = False
        try:
            if (self.isRuning):
                raise Exception("打包程序正在执行")
            gitUrl = config['git']['url']
            self.log.info("git.url:%s" % gitUrl)
            repo = {}
            # 同步代码
            if (os.path.exists(self.projectPath)):
                repo = git.Repo(self.projectPath)
                self.log.info("开始同步代码")
                origin = repo.remotes.origin
                res = origin.fetch()
                origin.pull()
                headcommit = repo.heads.master.commit
                self.log.info("更新后最后一次提交为:%s" % headcommit)
                if (headcommit == self.lastcommit):
                    change = False
                    self.log.info("没有代码更新")
                else:
                    change = True
                    self.log.info("有代码更新")
                self.log.info("同步代码完成")
            else:
                # 第一次的话克隆
                self.log.info("开始克隆代码")
                repo = git.Repo.clone_from(url=gitUrl, to_path=self.projectPath)
                self.log.info("首次克隆代码完成")
                change = True
            self.lastcommit = repo.heads.master.commit
            self.log.info("设置最后一次提交为:%s" % self.lastcommit)
        except Exception as e:
            change = False
            self.log.info("同步代码异常%s" % e)
        finally:
            return change

    def build(self):
        try:
            buildPath = os.path.join(self.basePath, self.projectPath)
            self.log.info("切换工作目录准备编译:%s" % buildPath)
            os.chdir(buildPath)
            self.log.info("开始NODEJS编译")
            # mavn编译文件
            env_dist = os.environ
            self.log.info(os.system('npm install && npm run build && tar -zcvf dist.zip ./dist/'))
        except Exception as e:
            raise e
        self.log.info("结束NODEJS编译")

    def uploadFile(self, section, server):
        try:
            # 获取文件信息
            locals = (self.basePath, self.projectPath, section['local'])
            local_file_path = os.path.normpath('/'.join(locals))
            remote_file_path = section['remote']
            self.log.info("basePath:%s" % self.basePath)
            self.log.info("projectPath:%s" % self.projectPath)
            self.log.info("local:%s" % local_file_path)
            self.log.info("remote:%s" % remote_file_path)
            if (os.path.exists(local_file_path) == False):
                raise Exception("未找到编译文件:%s" % local_file_path);
        except Exception:
            raise Exception("打包编译文件错误");

        try:
            # 开始连接ssh
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(server['ip'], username=server['user'], password=server['password'], allow_agent=True)
            # 上传文件到远程机
            self.log.info("开始上传文件到服务器:%s" % server['ip'])
            sftp = ssh.open_sftp()
            sftp.put(local_file_path, remote_file_path)
            sftp.close()
            self.log.info("结束上传文件")
            cmd = section['appctl'].strip()
            if (cmd.isspace() == False):
                self.log.info("开始执行远程命令:%s" % cmd)
                self.log.info(ssh.exec_command(cmd))
                self.log.info("完成远程命令")
        except Exception:
            raise

    def sync(self, config):
        try:
            if (self.isRuning):
                raise Exception("打包程序正在执行")
            self.isRuning = True
            self.log.info("打包程序开始执行")
            # self.gitClone(config)
            self.build()
            for sectionName in config['build']:
                self.syncOne(config,sectionName)
            self.isError = False
        except Exception as e:
            self.isError = True
            self.log.error("打包过程中发生错误:%s" % e)
        finally:
            self.log.info("打包程序完成")
            self.isRuning = False

    def syncOne(self, config, sectionName):
        try:
            self.log.info("查找到发布配置:%s" % sectionName)
            section = config['build'][sectionName]
            print(section)
            # 如果有cmd命令就执行
            if ('cmd' in section):
                self.log.info(os.system(section['cmd']))
            # 需要上传的服务地址
            for serverName in section['server']:
                server = config['server'][serverName]
                self.uploadFile(section, server)
            # 如果正常则删除错误信息
            if sectionName in self.errorConfigs:
                self.errorConfigs.pop(sectionName)
        except Exception:
            # 如果错误把错误信息放进去
            self.errorConfigs[sectionName] = section
            self.log.error("发布%s错误" % sectionName)
            raise Exception


# 开始执行方法
syncCode = SyncCode()
syncCode.autoSync()
