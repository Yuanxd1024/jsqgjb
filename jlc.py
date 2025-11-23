import os
import sys
import time
import json
import tempfile
import random
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 全局变量用于收集总结日志
in_summary = False
summary_logs = []

def log(msg):
    full_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(full_msg, flush=True)
    if in_summary:
        summary_logs.append(msg)  # 只收集纯消息，无时间戳

def format_nickname(nickname):
    """格式化昵称，只显示第一个字和最后一个字，中间用星号代替"""
    if not nickname or len(nickname.strip()) == 0:
        return "未知用户"
    
    nickname = nickname.strip()
    if len(nickname) == 1:
        return f"{nickname}*"
    elif len(nickname) == 2:
        return f"{nickname[0]}*"
    else:
        return f"{nickname[0]}{'*' * (len(nickname)-2)}{nickname[-1]}"

def get_user_nickname_from_api(driver):
    """通过API获取用户昵称"""
    try:
        # 获取当前页面的Cookie
        cookies = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'cookie': cookie_str
        }
        
        # 调用用户信息API
        response = requests.get("https://oshwhub.com/api/users", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('success'):
                nickname = data.get('result', {}).get('nickname', '')
                if nickname:
                    formatted_nickname = format_nickname(nickname)
                    log(f"👤 昵称: {formatted_nickname}")
                    return formatted_nickname
        
        log(f"⚠ 无法获取用户昵称")
        return None
    except Exception as e:
        log(f"⚠ 获取用户昵称失败: {e}")
        return None

def ensure_login_page(driver):
    """确保进入登录页面，如果未检测到登录页面则重启浏览器"""
    max_restarts = 5
    restarts = 0
    
    while restarts < max_restarts:
        try:
            driver.get("https://oshwhub.com/sign_in")
            log("已打开 JLC 签到页")
            
            WebDriverWait(driver, 10).until(lambda d: "passport.jlc.com/login" in d.current_url)
            current_url = driver.current_url

            # 检查是否在登录页面
            if "passport.jlc.com/login" in current_url:
                log("✅ 检测到未登录状态")
                return True
            else:
                restarts += 1
                if restarts < max_restarts:
                    # 静默重启浏览器
                    driver.quit()
                    
                    # 重新初始化浏览器
                    chrome_options = Options()
                    chrome_options.add_argument("--headless=new")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--window-size=1920,1080")
                    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
                    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
                    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    chrome_options.add_experimental_option('useAutomationExtension', False)

                    caps = DesiredCapabilities.CHROME
                    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
                    
                    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    
                    # 静默等待后继续循环
                    time.sleep(2)
                else:
                    log("❌ 重启浏览器{max_restarts}次后仍无法进入登录页面")
                    return False
                    
        except Exception as e:
            restarts += 1
            if restarts < max_restarts:
                try:
                    driver.quit()
                except:
                    pass
                
                # 重新初始化浏览器
                chrome_options = Options()
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_argument("--blink-settings=imagesEnabled=false")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)

                caps = DesiredCapabilities.CHROME
                caps['goog:loggingPrefs'] = {'performance': 'ALL'}
                
                driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                time.sleep(2)
            else:
                log(f"❌ 重启浏览器{max_restarts}次后仍出现异常: {e}")
                return False
    
    return False

def check_password_error(driver):
    """检查页面是否显示密码错误提示"""
    try:
        # 等待可能出现的错误提示元素
        error_selectors = [
            "//*[contains(text(), '账号或密码不正确')]",
            "//*[contains(text(), '用户名或密码错误')]",
            "//*[contains(text(), '密码错误')]",
            "//*[contains(text(), '登录失败')]",
            "//*[contains(@class, 'error')]",
            "//*[contains(@class, 'err-msg')]",
            "//*[contains(@class, 'toast')]",
            "//*[contains(@class, 'message')]"
        ]
        
        for selector in error_selectors:
            try:
                # 使用短暂的等待来检查错误提示
                error_element = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if error_element.is_displayed():
                    error_text = error_element.text.strip()
                    if any(keyword in error_text for keyword in ['账号或密码不正确', '用户名或密码错误', '密码错误', '登录失败']):
                        log("❌ 检测到账号或密码错误")
                        return True
            except:
                continue
                
        return False
    except Exception as e:
        log(f"⚠ 检查密码错误时出现异常: {e}")
        return False

def safe_click_element(driver, element, element_name):
    """安全点击元素，使用多种方法尝试"""
    try:
        # 方法1: 直接使用JavaScript点击
        driver.execute_script("arguments[0].click();", element)
        log(f"✅ 使用JavaScript点击{element_name}")
        return True
    except Exception as e1:
        log(f"⚠ JavaScript点击失败，尝试其他方法: {e1}")
        
        try:
            # 方法2: 使用ActionChains点击
            actions = ActionChains(driver)
            actions.move_to_element(element).click().perform()
            log(f"✅ 使用ActionChains点击{element_name}")
            return True
        except Exception as e2:
            log(f"⚠ ActionChains点击失败: {e2}")
            
            try:
                # 方法3: 滚动到元素并尝试直接点击
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(1)
                element.click()
                log(f"✅ 使用标准点击{element_name}")
                return True
            except Exception as e3:
                log(f"❌ 所有点击方法都失败: {e3}")
                return False

def sign_in_account(username, password):
    """为单个账号执行完整的登录流程"""
    log("开始处理账号")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 25)
    
    # 记录详细结果
    result = {
        'nickname': '未知',
        'login_success': False,
        'password_error': False
    }

    try:
        # 1. 确保进入登录页面
        if not ensure_login_page(driver):
            result['login_success'] = False
            return result, driver

        current_url = driver.current_url

        # 2. 登录流程
        log("检测到未登录状态，正在执行登录流程...")

        try:
            phone_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
            )
            phone_btn.click()
            log("已切换账号登录")
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]')))
        except Exception as e:
            log(f"账号登录按钮可能已默认选中: {e}")

        # 输入账号密码
        try:
            user_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]'))
            )
            user_input.clear()
            user_input.send_keys(username)

            pwd_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))
            )
            pwd_input.clear()
            pwd_input.send_keys(password)
            log("已输入账号密码")
        except Exception as e:
            log(f"❌ 登录输入框未找到: {e}")
            result['login_success'] = False
            return result, driver

        # 点击登录
        try:
            login_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit"))
            )
            login_btn.click()
            log("已点击登录按钮")
        except Exception as e:
            log(f"❌ 登录按钮定位失败: {e}")
            result['login_success'] = False
            return result, driver

        # 立即检查密码错误提示（点击登录按钮后）
        time.sleep(1)  # 给错误提示一点时间显示
        if check_password_error(driver):
            result['password_error'] = True
            result['login_success'] = False
            return result, driver

        # 处理滑块验证
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_slide")))
        try:
            slider = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn_slide"))
            )
            
            track = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".nc_scale"))
            )
            
            track_width = track.size['width']
            slider_width = slider.size['width']
            move_distance = track_width - slider_width - 10
            
            log(f"检测到滑块验证码，滑动距离: {move_distance}px")
            
            actions = ActionChains(driver)
            actions.click_and_hold(slider).perform()
            time.sleep(0.5)
            
            quick_distance = int(move_distance * random.uniform(0.6, 0.8))
            slow_distance = move_distance - quick_distance
            
            y_offset1 = random.randint(-2, 2)
            actions.move_by_offset(quick_distance, y_offset1).perform()
            time.sleep(random.uniform(0.1, 0.3))
            
            y_offset2 = random.randint(-2, 2)
            actions.move_by_offset(slow_distance, y_offset2).perform()
            time.sleep(random.uniform(0.05, 0.15))
            
            actions.release().perform()
            log("滑块拖动完成")
            
            # 滑块验证后立即检查密码错误提示
            time.sleep(1)  # 给错误提示一点时间显示
            if check_password_error(driver):
                result['password_error'] = True
                result['login_success'] = False
                return result, driver
                
            WebDriverWait(driver, 10).until(lambda d: "oshwhub.com" in d.current_url and "passport.jlc.com" not in d.current_url)
            
        except Exception as e:
            log(f"滑块验证处理: {e}")
            # 滑块验证失败后检查密码错误
            time.sleep(1)
            if check_password_error(driver):
                result['password_error'] = True
                result['login_success'] = False
                return result, driver

        # 等待跳转
        log("等待登录跳转...")
        max_wait = 15
        jumped = False
        for i in range(max_wait):
            current_url = driver.current_url
            
            # 检查是否成功跳转回签到页面
            if "oshwhub.com" in current_url and "passport.jlc.com" not in current_url:
                log("成功跳转回签到页面")
                jumped = True
                break
            
            time.sleep(1)
        
        if not jumped:
            current_title = driver.title
            log(f"❌ 跳转超时，当前页面标题: {current_title}")
            result['login_success'] = False
            return result, driver

        # 3. 获取用户昵称
        time.sleep(1)
        nickname = get_user_nickname_from_api(driver)
        if nickname:
            result['nickname'] = nickname
        else:
            result['nickname'] = '未知'

        result['login_success'] = True
        log("✅ 登录成功")
        
        # 4. 打开新标签页进入活动页面
        log("打开新标签页进入活动页面...")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        activity_url = "https://www.jlc.com/portal/anniversary-doubleActivity?spm=PCB.Homepage.banner.1003"
        driver.get(activity_url)
        log(f"已打开活动页面: {activity_url}")
        
        # 5. 等待页面完全加载并额外等待10秒
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        log("页面加载完成，额外等待10秒...")
        time.sleep(10)
        
        # 6. 注入并执行秒杀脚本
        log("开始注入秒杀脚本...")
        seckill_script = """
(function() {
'use strict';

// ================= 配置区域 =================  
const CONFIG = {  
    // 必填项：活动/分类ID  
    activityAccessId: "b51c4cf07b794278a79092674af8b563",   

    // 目标商品的 SKU Code  
    targetSku: "SKUJC6",   

    // 并发突发请求数量：在开抢时，脚本会立即发送这个数量的请求。  
    // 就30吧，立创服务器太拉了，太多别给他干爆了  
    BURST_COUNT: 30,   

    // 提前多少毫秒开始预热请求 (Lead Time)  
    leadTime: 300  
};  

// 接口地址  
const URLS = {  
    list: "/api/integral/seckill/ns/getSeckillGoods",  
    buy: "/api/integral/seckill/exchangeSeckillGoods"  
};  

console.log(`%c 🚀 嘉立创秒杀脚本 By zhangMonday 已加载 [目标SKU: ${CONFIG.targetSku}]`, "background: #222; color: #00ff00; font-size:14px;");  
console.log(`🔑 已使用活动 ID: ${CONFIG.activityAccessId}`);  
console.log(`🔥 轰炸数量: ${CONFIG.BURST_COUNT} 次`);  

// ================= 通用请求函数 =================  
async function fetchJson(url, data) {  
    try {  
        const response = await fetch(url, {  
            method: "POST",  
            headers: { "Content-Type": "application/json" },  
            body: JSON.stringify(data)  
        });  
        return await response.json();  
    } catch (e) {  
        // 异步请求失败不影响其他请求  
        return { error: true, message: e.message };  
    }  
}  

// ================= 调试/自检功能 (checkSystem) =================  
async function checkSystem() {  
    console.log("%c 🔍 开始系统自检...", "font-weight:bold; font-size:16px; color: #1890ff;");  

    // [1/3] 列表  
    console.log("%c[1/3] 正在请求商品列表...", "color: gray");  
    const listPayload = { categoryAccessId: CONFIG.activityAccessId };  
    const listRes = await fetchJson(URLS.list, listPayload);  
    console.log("📄 列表接口返回:", listRes);  

    if (!listRes.data || !listRes.data.seckillGoodsResponseVos) {  
        throw new Error("❌ 列表获取失败，请检查 activityAccessId 或登录状态");  
    }  

    // [2/3] 验证 SKU  
    const target = listRes.data.seckillGoodsResponseVos.find(item => item.skuCode === CONFIG.targetSku);  
    if (!target) {  
        throw new Error(`❌ 未找到 SKU 为 [${CONFIG.targetSku}] 的商品。`);  
    }  
    console.log(`✅ [2/3] SKU匹配成功: ${target.skuTitle}`);  
      
    // [3/3] 测试抢购接口 (单次发送)  
    console.log("%c[3/3] 正在模拟一次抢购请求 (测试 Payload)...", "color: orange");  
    const buyPayload = {  
        "goodsDetailAccessId": target.voucherSeckillActivityDetailAccessId,  
        "categoryAccessId": CONFIG.activityAccessId,  
        "source": 4  
    };  
    console.log("📦 发送的抢购请求体:", buyPayload);  

    const buyRes = await fetchJson(URLS.buy, buyPayload);  
    console.log("📡 抢购接口返回:", buyRes);  

    if (buyRes.code === 200 && buyRes.success) {  
        console.log("%c 🎉 我操居然抢购成功了！", "color: red; font-weight:bold");  
    } else {  
        console.log(`ℹ️ 预期结果 (如果活动未开始): ${buyRes.message || "未知错误"}`);  
        console.log("%c ✅ 接口链路通畅，Payload 格式已确认无误。", "color: green; font-weight:bold");  
    }  
}  

// ================= 核心执行函数 (执行抢购) =================  
// 此函数现在返回 Promise，用于并发调用  
function executeSeckill(goodsDetailAccessId) {  
    const payload = {  
        "goodsDetailAccessId": goodsDetailAccessId,  
        "categoryAccessId": CONFIG.activityAccessId,  
        "source": 4  
    };  

    // 仅在第一次打印 payload 确认  
    if(!window.hasLoggedPayload) {  
        console.log("💣 准备发送的最终 Payload:", JSON.stringify(payload));  
        window.hasLoggedPayload = true;  
    }  
      
    return fetchJson(URLS.buy, payload);  
}  

// ================= 正式抢购流程=================  
async function startJLCSeckill() {  
    console.log("🚀 启动正式抢购流程...");  
      
    // 1. 获取商品信息并进行时间同步  
    const listPayload = { categoryAccessId: CONFIG.activityAccessId };  
      
    const listReqStart = Date.now(); // 记录本地请求开始时间  
    const listRes = await fetchJson(URLS.list, listPayload);  
    const listReqEnd = Date.now();   // 记录本地请求结束时间  
      
    if(!listRes.data) return console.error("❌ 无法获取列表，请检查 Activity ID 或登录状态");  
      
    const target = listRes.data.seckillGoodsResponseVos.find(item => item.skuCode === CONFIG.targetSku);  
    if(!target) return console.error("❌ 找不到目标商品 SKU，请检查 CONFIG.targetSku");  

    const goodsDetailAccessId = target.voucherSeckillActivityDetailAccessId;  

    // 2. 时间校准计算  
    const serverTime = new Date(listRes.data.currentTime).getTime();  
    const activityStartTime = new Date(listRes.data.activityBeginTime).getTime();  

    const RTT = listReqEnd - listReqStart;  
    const localTimeAtServerSend = listReqEnd - RTT / 2;  
    const timeDelta = serverTime - localTimeAtServerSend;   
      
    const adjustedStartTime = activityStartTime - timeDelta;   
    const trueTimeLeft = adjustedStartTime - Date.now();  

    // 3. 显示时间信息  
    console.log(`\\n===== 🕒 时间同步与调度 =====`);  
    console.log(`⏱️ 服务器当前时间: ${new Date(serverTime).toLocaleTimeString('zh-CN', { hour12: false })}.${serverTime % 1000}`);  
    console.log(`⏰ 预期开抢时间: ${new Date(activityStartTime).toLocaleTimeString('zh-CN', { hour12: false })}.${activityStartTime % 1000}`);  
    console.log(`⚙️ 服务器/本地时差 (Server - Local): ${timeDelta.toFixed(0)} ms`);  
    console.log(`=============================`);  

    // 4. 定义执行器 (并发)  
    const run = () => {  
        console.log(`🔥 启动并发轰炸！立即发送 ${CONFIG.BURST_COUNT} 个请求...`);  
        let stop = false;  
        let count = 0;  
          
        // Success handler for all concurrent Promises  
        const handleSuccess = (res) => {  
            if (res.code === 200 && res.success && !stop) {  
                stop = true;  
                // 在成功后设置一个小的定时器，确保停止计时器  
                setTimeout(() => {  
                    console.log(`%c 🎉🎉🎉 牛逼抢到了！总共发送 ${count} 次请求！ 🎉🎉🎉`, "font-size: 30px; color: red; font-weight: bold;");  
                    alert("抢购成功！");  
                }, 50);   
            }  
        };  
          
        // 发送请求突发循环 (Fire and Forget)  
        for (let i = 0; i < CONFIG.BURST_COUNT; i++) {  
            if (stop) break;  
            count++;  
              
            executeSeckill(goodsDetailAccessId)  
                .then(handleSuccess)  
                .catch(e => { /* 忽略网络层面的错误 */ });   
        }  

        // 15秒后停止 (检查计时器来停止，以防成功处理失败)  
        setTimeout(() => {  
            if(!stop) {  
                stop = true;  
                console.log(`🛑 停止请求（超时保护）。共计尝试发送 ${count} 次请求。没显示牛逼抢到了就是妹成功，哎`);  
            }  
        }, 15000);  
    };  

    // 5. 倒计时调度  
    if (trueTimeLeft <= CONFIG.leadTime) {  
        run();  
    } else {  
        setTimeout(run, trueTimeLeft - CONFIG.leadTime);  
        console.log(`⏳ 定时器已设置，将在 ${ (trueTimeLeft - CONFIG.leadTime)/1000 } 秒后启动抢购...`);  
    }  
}  

// 自动执行自检和抢购  
(async () => {  
    try {  
        await checkSystem();  
        console.log("%c ✅ 自检通过，自动启动抢购流程...", "color: green; font-weight:bold");  
        await startJLCSeckill();  
    } catch (e) {  
        console.error("❌ 脚本执行失败:", e.message);  
    }  
})();

})();
"""
        
        # 执行秒杀脚本
        driver.execute_script(seckill_script)
        log("✅ 秒杀脚本已注入并执行")

    except Exception as e:
        log(f"❌ 程序执行错误: {e}")
        result['login_success'] = False
    
    return result, driver

def wait_until_10_05():
    """等待直到北京时间10:05"""
    while True:
        now = datetime.now()
        if now.hour == 10 and now.minute >= 5:
            log("🕙 北京时间10:05已到，程序正常退出")
            return True
        time_left = (10 - now.hour) * 3600 + (5 - now.minute) * 60 - now.second
        if time_left > 0:
            log(f"⏰ 等待北京时间10:05，剩余时间: {time_left//60}分{time_left%60}秒")
            time.sleep(min(60, time_left))  # 最多等待1分钟再检查
        else:
            break

def main():
    global in_summary
    
    if len(sys.argv) < 3:
        print("用法: python jlc_seckill.py 账号 密码")
        print("示例: python jlc_seckill.py user1 pwd1")
        sys.exit(1)
    
    username = sys.argv[1].strip()
    password = sys.argv[2].strip()
    
    log(f"开始处理账号秒杀任务")
    
    # 执行登录和脚本注入
    result, driver = sign_in_account(username, password)
    
    if result.get('password_error'):
        log("❌ 账号或密码错误，程序退出")
        if driver:
            driver.quit()
        sys.exit(1)
    
    if not result['login_success']:
        log("❌ 登录失败，程序退出")
        if driver:
            driver.quit()
        sys.exit(1)
    
    # 等待直到10:05
    try:
        log("🎯 秒杀脚本已启动，等待抢购完成...")
        wait_until_10_05()
    except KeyboardInterrupt:
        log("⏹️ 用户中断程序")
    finally:
        if driver:
            driver.quit()
            log("浏览器已关闭")
    
    log("✅ 程序正常退出")
    sys.exit(0)

if __name__ == "__main__":
    main()
