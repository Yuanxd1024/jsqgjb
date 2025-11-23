import os
import sys
import time
import random
import json
from datetime import datetime, timedelta
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log(msg):
    full_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(full_msg, flush=True)

def with_retry(func, max_retries=5, delay=1):
    """如果函数返回None或抛出异常，静默重试"""
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    return result
                time.sleep(delay + random.uniform(0, 1))
            except Exception:
                time.sleep(delay + random.uniform(0, 1))
        return None
    return wrapper

@with_retry
def extract_token_from_local_storage(driver):
    try:
        token = driver.execute_script("return window.localStorage.getItem('X-JLC-AccessToken');")
        if token:
            log(f"✅ 成功从 localStorage 提取 token: {token[:30]}...")
            return token
        else:
            alternative_keys = ["x-jlc-accesstoken", "accessToken", "token", "jlc-token"]
            for key in alternative_keys:
                token = driver.execute_script(f"return window.localStorage.getItem('{key}');")
                if token:
                    log(f"✅ 从 localStorage 的 {key} 提取到 token: {token[:30]}...")
                    return token
    except Exception as e:
        log(f"❌ 从 localStorage 提取 token 失败: {e}")
    return None

def get_chrome_options():
    """统一获取 Chrome 配置，加强防检测"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 【关键修改1】设置真实浏览器的 User-Agent，去除 Headless 特征
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Selenium 4+ 方式开启日志
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL', 'browser': 'ALL'})
    
    return chrome_options

def ensure_login_page(driver):
    """确保进入登录页面，如果未检测到登录页面则重启浏览器"""
    max_restarts = 5
    restarts = 0
    
    while restarts < max_restarts:
        try:
            # 注入反检测脚本
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            driver.get("https://passport.jlc.com/login?appId=JLC_PORTAL_PC&redirectUrl=https%3A%2F%2Fwww.jlc.com%2F&bizExtendedParam=%7B%22jlcGroup_source%22%3A%22jlc%22%7D")
            log("已打开 JLC 登录页")
            
            WebDriverWait(driver, 10).until(lambda d: "passport.jlc.com/login" in d.current_url)
            current_url = driver.current_url

            if "passport.jlc.com/login" in current_url:
                log("✅ 检测到登录页面")
                return True
            else:
                raise Exception("未停留在登录页")
                    
        except Exception as e:
            restarts += 1
            log(f"⚠️ 无法进入登录页 (尝试 {restarts}/{max_restarts}): {e}")
            try:
                driver.quit()
            except:
                pass
            
            if restarts < max_restarts:
                options = get_chrome_options()
                driver = webdriver.Chrome(options=options)
                time.sleep(2)
            else:
                log("❌ 多次重启后仍无法进入登录页面")
                return False
    return False

def check_password_error(driver):
    """检查页面是否显示密码错误提示"""
    try:
        error_selectors = [
            "//*[contains(text(), '账号或密码不正确')]",
            "//*[contains(text(), '用户名或密码错误')]",
            "//*[contains(text(), '密码错误')]",
            "//*[contains(text(), '登录失败')]",
            "//*[contains(@class, 'err-msg')]",
            "//*[contains(@class, 'toast')]"
        ]
        
        for selector in error_selectors:
            try:
                error_element = WebDriverWait(driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                if error_element.is_displayed():
                    log(f"❌ 检测到错误提示: {error_element.text}")
                    return True
            except:
                continue
        return False
    except Exception:
        return False

def perform_login(driver, username, password):
    wait = WebDriverWait(driver, 25)
    
    if not ensure_login_page(driver):
        return False

    log("正在执行登录流程...")

    try:
        phone_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"账号登录")]'))
        )
        phone_btn.click()
        log("已切换账号登录")
    except:
        log("默认可能已是账号登录，继续...")

    # 输入账号密码
    try:
        user_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@placeholder="请输入手机号码 / 客户编号 / 邮箱"]')))
        user_input.clear()
        user_input.send_keys(username)

        pwd_input = wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="password"]')))
        pwd_input.clear()
        pwd_input.send_keys(password)
        log("已输入账号密码")
    except Exception as e:
        log(f"❌ 登录输入框未找到: {e}")
        return False

    # 点击登录
    try:
        login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.submit")))
        login_btn.click()
        log("已点击登录按钮")
    except Exception as e:
        log(f"❌ 登录按钮定位失败: {e}")
        return False

    time.sleep(1)
    if check_password_error(driver):
        return False

    # 处理滑块验证
    try:
        # 检查是否出现滑块（等待时间缩短，如果没有滑块则直接跳过）
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_slide")))
        except:
            log("未检测到滑块，检查是否已直接跳转...")
            if "passport.jlc.com" not in driver.current_url:
                log("✅ 无需滑块，已直接登录成功")
                return True
            # 如果还在登录页且没滑块，可能是其他问题，抛出让外层捕获
            raise Exception("登录页停留且无滑块")

        slider = driver.find_element(By.CSS_SELECTOR, ".btn_slide")
        track = driver.find_element(By.CSS_SELECTOR, ".nc_scale")
        
        track_width = track.size['width']
        slider_width = slider.size['width']
        move_distance = track_width - slider_width - 5 # 稍微留一点余量
        
        log(f"检测到滑块，滑动距离: {move_distance}px")
        
        actions = ActionChains(driver)
        actions.click_and_hold(slider).perform()
        time.sleep(0.2)
        
        # 模拟人类轨迹：先快后慢
        tracks = []
        current = 0
        mid = move_distance * 0.75
        t = 0.2
        v = 0
        
        while current < move_distance:
            if current < mid:
                a = 2
            else:
                a = -3
            v0 = v
            v = v0 + a * t
            move = v0 * t + 0.5 * a * t * t
            current += move
            tracks.append(round(move))
        
        # 执行滑动
        for x in tracks:
            actions.move_by_offset(x, 0).perform()
            # 极短的随机停顿
            # time.sleep(random.uniform(0.005, 0.01)) 
        
        # 稍微修正最后的位置
        actions.move_by_offset(move_distance - sum(tracks), 0).perform()
        time.sleep(0.5)
        actions.release().perform()
        log("滑块拖动完成，等待验证结果...")
        
        # 【关键修改2】滑块后可能需要再次点击登录，或者等待自动跳转
        time.sleep(2)
        
        # 如果还在登录页，尝试再次点击登录按钮（防止滑块验证通过但未提交）
        if "passport.jlc.com" in driver.current_url:
            log("页面未跳转，尝试再次点击登录按钮...")
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, "button.submit")
                login_btn.click()
            except:
                pass
        
    except Exception as e:
        log(f"滑块处理流程异常 (非致命): {e}")
        time.sleep(1)
        if check_password_error(driver):
            return False

    # 等待跳转
    log("等待登录跳转...")
    max_wait = 20
    jumped = False
    for i in range(max_wait):
        current_url = driver.current_url
        if "www.jlc.com" in current_url and "passport.jlc.com" not in current_url:
            log("✅ 成功跳转回首页")
            jumped = True
            break
        time.sleep(1)
    
    if not jumped:
        log(f"❌ 跳转超时，当前URL: {driver.current_url}")
        return False

    return True

def main():
    if len(sys.argv) < 5:
        print("用法: python jlc.py 账号 密码 SKU 活动ID")
        sys.exit(1)
    
    username = sys.argv[1].strip()
    password = sys.argv[2].strip()
    target_sku = sys.argv[3].strip()
    activity_id = sys.argv[4].strip()
    
    log(f"🚀 启动任务 | 账号: {username} | 目标SKU: {target_sku}")
    
    options = get_chrome_options()
    driver = webdriver.Chrome(options=options)
    
    # 再次确保反检测 JS 被执行
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    try:
        if not perform_login(driver, username, password):
            log("❌ 登录失败，程序退出")
            sys.exit(1)
        
        driver.get("https://www.jlc.com/portal/anniversary-doubleActivity")
        log("已跳转到活动页面")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # JS 脚本模板
        raw_js_script = """
(function() {
'use strict';
const CONFIG = {  
    activityAccessId: "REPLACE_ACTIVITY_ID",   
    targetSku: "REPLACE_TARGET_SKU",   
    BURST_COUNT: 30,   
    leadTime: 300  
};  
const URLS = {  
    list: "/api/integral/seckill/ns/getSeckillGoods",  
    buy: "/api/integral/seckill/exchangeSeckillGoods"  
};  
console.log(`%c 🚀 嘉立创秒杀脚本已加载 [目标SKU: ${CONFIG.targetSku}]`, "color: #00ff00; font-size:14px;");  

async function fetchJson(url, data) {  
    try {  
        const response = await fetch(url, {  
            method: "POST",  
            headers: { "Content-Type": "application/json" },  
            body: JSON.stringify(data)  
        });  
        return await response.json();  
    } catch (e) { return { error: true, message: e.message }; }  
}  

async function checkSystem() {  
    console.log("🔍 开始自检...");  
    const listPayload = { categoryAccessId: CONFIG.activityAccessId };  
    const listRes = await fetchJson(URLS.list, listPayload);  
    
    if (!listRes.data || !listRes.data.seckillGoodsResponseVos) {  
        throw new Error("❌ 列表获取失败，请检查 activityAccessId 或登录状态");  
    }  

    const target = listRes.data.seckillGoodsResponseVos.find(item => item.skuCode === CONFIG.targetSku);  
    if (!target) throw new Error(`❌ 未找到 SKU [${CONFIG.targetSku}]`);  
    console.log(`✅ SKU匹配成功: ${target.skuTitle}`);  
    return target.voucherSeckillActivityDetailAccessId;
}  

function executeSeckill(goodsDetailAccessId) {  
    return fetchJson(URLS.buy, {  
        "goodsDetailAccessId": goodsDetailAccessId,  
        "categoryAccessId": CONFIG.activityAccessId,  
        "source": 4  
    });  
}  

async function startJLCSeckill() {  
    try {
        const goodsDetailAccessId = await checkSystem();
        console.log("🚀 准备就绪，开始同步时间...");
        
        const listRes = await fetchJson(URLS.list, { categoryAccessId: CONFIG.activityAccessId });
        const serverTime = new Date(listRes.data.currentTime).getTime();  
        const activityStartTime = new Date(listRes.data.activityBeginTime).getTime();  
        
        // 简单的时间校准
        const timeDelta = serverTime - Date.now();
        const adjustedStartTime = activityStartTime - timeDelta;
        const trueTimeLeft = adjustedStartTime - Date.now();

        console.log(`⏰ 距离开抢还有: ${trueTimeLeft} ms`);

        const run = () => {  
            console.log(`🔥 立即发送 ${CONFIG.BURST_COUNT} 个请求!`);  
            let stop = false;  
            let successCount = 0;
            
            for (let i = 0; i < CONFIG.BURST_COUNT; i++) {  
                if (stop) break;  
                executeSeckill(goodsDetailAccessId).then(res => {
                    if (res.code === 200 && res.success) {
                        stop = true;
                        console.log("%c 🎉 抢购成功！", "color: red; font-size: 20px;");
                    }
                });
            }  
        };  

        if (trueTimeLeft <= CONFIG.leadTime) {  
            run();  
        } else {  
            setTimeout(run, trueTimeLeft - CONFIG.leadTime);  
        }
    } catch(e) {
        console.error(e.message);
    }
}  

startJLCSeckill();
})();
"""
        js_script = raw_js_script.replace("REPLACE_ACTIVITY_ID", activity_id)\
                                 .replace("REPLACE_TARGET_SKU", target_sku)
        
        driver.execute_script(js_script)
        log("JS脚本已注入并执行")
        
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        target_time = now.replace(hour=10, minute=5, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        
        log(f"程序将等待直到 {target_time.strftime('%H:%M:%S')} 后退出")
        
        last_logs = []
        while datetime.now(beijing_tz) < target_time:
            try:
                browser_logs = driver.get_log('browser')
                new_logs = [entry for entry in browser_logs if entry not in last_logs]
                for entry in new_logs:
                    log(f"浏览器: {entry['message']}")
                last_logs.extend(new_logs)
            except:
                pass
            time.sleep(1)
        
        log("程序正常退出")
        sys.exit(0)
    
    except Exception as e:
        log(f"❌ 程序执行错误: {e}")
        sys.exit(1)
    finally:
        driver.quit()
        log("浏览器已关闭")

if __name__ == "__main__":
    main()
